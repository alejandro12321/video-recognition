import tkinter as tk
from tkinter import filedialog
import shutil
import os
from moviepy.editor import VideoFileClip
import glob
import threading
import boto3
import time
from collections import defaultdict
from multiprocessing import Pool

# Configura las credenciales de AWS
aws_access_key_id = 'AKIAYS2NXMALTGEWAEG4'
aws_secret_access_key = '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'
region_name = 'us-east-1'

# Configura el nombre del bucket de S3
bucket_name = 'mybucket01011'
role_arn = 'arn:aws:iam::590184144919:role/RekognitionVideo'
specific_objects = ["Car", "Gun", "Phone"]  # Objetos específicos a buscar

# Crea el cliente de Rekognition
rekognition_client = boto3.client(
    'rekognition',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)
# Diccionarios para almacenar las métricas
celebrity_metrics = defaultdict(lambda: {'count': 0, 'total_time': 0})
object_metrics = defaultdict(lambda: {'count': 0, 'total_time': 0})

def start_celebrity_recognition(video_file_name):
    """
        Inicia el reconocimiento de celebridades en un archivo de video.

        :param video_file_name: Nombre del archivo de video en S3
        :return: ID del trabajo de reconocimiento de celebridades
        """
    response = rekognition_client.start_celebrity_recognition(
        Video={'S3Object': {'Bucket': bucket_name, 'Name': video_file_name}},
        # Eliminamos NotificationChannel y RoleArn
    )
    return response['JobId']

# Función para obtener los resultados del reconocimiento de celebridades
def get_celebrity_recognition_results(job_id, max_celebs=2):
    """
    Obtiene los resultados del reconocimiento de celebridades para un trabajo dado de cantidad fija máxima de celebridades.

    :param job_id: ID del trabajo de reconocimiento de celebridades
    :return: Lista de celebridades detectadas
    """
    while True:
        response = rekognition_client.get_celebrity_recognition(JobId=job_id)
        status = response['JobStatus']
        if status == 'SUCCEEDED':
            return response['Celebrities'][:max_celebs]
        elif status == 'FAILED':
            print("Celebrity recognition job failed")
            return None
        time.sleep(5)

# Función para iniciar la detección de etiquetas en un archivo de video
def start_label_detection(video_file_name):
    response = rekognition_client.start_label_detection(
        Video={'S3Object': {'Bucket': bucket_name, 'Name': video_file_name}},
        MinConfidence=50,
        JobTag='LabelDetection',
        # Eliminamos NotificationChannel y RoleArn
    )
    return response['JobId']

# Función para obtener los resultados de la detección de etiquetas
def get_label_detection_results(job_id):
    while True:
        response = rekognition_client.get_label_detection(JobId=job_id)
        status = response['JobStatus']
        if status == 'SUCCEEDED':
            return response['Labels']
        elif status == 'FAILED':
            print("Label detection job failed")
            return None
        time.sleep(5)

# Función para abrir un diálogo de selección de archivo
def open_file_dialog():
    file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
    if file_path:
        shutil.copy(file_path, os.path.join("src", os.path.basename(file_path)))
        print(f"File copied to src folder: {os.path.basename(file_path)}")
        text_area.insert(tk.END, f"Selected file: {file_path}\n")
        process_button.config(state=tk.NORMAL)
    else:
        print("No file selected.")


def process_part(video_path, part_name, start, end):
    video = VideoFileClip(video_path)
    part = video.subclip(start, end)
    part_path = os.path.join("src", part_name)
    part.write_videofile(part_path, codec="libx264", audio_codec="aac")

    # Upload each part to S3
    s3_client = boto3.client('s3')
    s3_client.upload_file(part_path, bucket_name, part_name)

    # Perform celebrity recognition and label detection on each part
    celeb_job_id = start_celebrity_recognition(part_name)
    labels_job_id = start_label_detection(part_name)

    # Get results
    celebrities = get_celebrity_recognition_results(celeb_job_id)
    labels = get_label_detection_results(labels_job_id)

    video.close()
    return part_name, celebrities, labels


# Función para procesar un archivo de video
def process_video(file_path):
    text_area.insert(tk.END, "Processing...\n")
    select_button.config(state=tk.DISABLED)
    process_button.config(state=tk.DISABLED)

    video = VideoFileClip(file_path)
    duration = video.duration

    # Calculate the start and end times for each part
    part_duration = duration / 4
    part_times = [(i * part_duration, (i + 1) * part_duration) for i in range(4)]

    # Use multiprocessing to process video parts in parallel
    pool = Pool(processes=4)
    results = []

    for i, (start, end) in enumerate(part_times):
        part_name = f"part{i + 1}.mp4"
        results.append(pool.apply_async(process_part, args=(file_path, part_name, start, end)))

    pool.close()
    pool.join()

    for result in results:
        part_name, celebrities, labels = result.get()
        text_area.insert(tk.END, f"Processed {part_name}\n")

        # Update and display metrics for celebrities
        if celebrities:
            for celeb in celebrities:
                timestamp_seconds = celeb['Timestamp'] / 1000
                name = celeb['Celebrity']['Name']
                confidence = celeb['Celebrity']['Confidence']
                text_area.insert(tk.END,
                                 f"Timestamp: {timestamp_seconds:.2f} seconds - Celebrity: {name} - Confidence: {confidence}\n")
                celebrity_metrics[name]['count'] += 1
                celebrity_metrics[name]['total_time'] += timestamp_seconds

        # Update and display metrics for labels
        if labels:
            for label in labels:
                name = label['Label']['Name']
                if name in specific_objects:
                    timestamp_seconds = label['Timestamp'] / 1000
                    confidence = label['Label']['Confidence']
                    text_area.insert(tk.END,
                                     f"Timestamp: {timestamp_seconds:.2f} seconds - Label: {name} - Confidence: {confidence}\n")
                    object_metrics[name]['count'] += 1
                    object_metrics[name]['total_time'] += timestamp_seconds

    text_area.insert(tk.END, "Processing complete.\n")
    generate_report()
    select_button.config(state=tk.NORMAL)
    process_button.config(state=tk.NORMAL)

def generate_report():
    text_area.insert(tk.END, "\n--- Metrics Report ---\n")
    text_area.insert(tk.END, "\n- Celebrities \n")
    for name, metrics in celebrity_metrics.items():
        text_area.insert(tk.END, f"Celebrity: {name} - Appearances: {metrics['count']} - Total Time: {metrics['total_time']:.2f} seconds\n")
    text_area.insert(tk.END, "\n -Object\n")
    for name, metrics in object_metrics.items():
        text_area.insert(tk.END, f"Object: {name} - Appearances: {metrics['count']} - Total Time: {metrics['total_time']:.2f} seconds\n")


def main():
    global text_area, process_button, select_button

    root = tk.Tk()
    root.title("MP4 File Selector")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width = 800
    height = 500
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    select_button = tk.Button(root, text="Select MP4 File", command=open_file_dialog, bg="#FFD09F")
    select_button.pack(side=tk.LEFT, padx=20, pady=20)

    process_button = tk.Button(root, text="Process File", state=tk.DISABLED, bg="#ABFF9F",
                               command=lambda: threading.Thread(target=process_video, args=(max(glob.glob("src/*.mp4"), key=os.path.getctime),)).start())
    process_button.pack(side=tk.LEFT, padx=20, pady=20)

    text_area = tk.Text(root, height=300, width=500)
    text_area.pack(padx=20, pady=(0, 20))

    root.mainloop()

if __name__ == '__main__':
    main()
