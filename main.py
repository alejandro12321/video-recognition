import tkinter as tk
from tkinter import filedialog
import shutil
import os
from moviepy.editor import VideoFileClip
import glob
import threading

global text_area, process_button, select_button
def open_file_dialog():
    file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
    if file_path:
        shutil.copy(file_path, os.path.join("src", os.path.basename(file_path)))
        print(f"File copied to src folder: {os.path.basename(file_path)}")
        text_area.insert(tk.END, f"Selected file: {file_path}\n")
        process_button.config(state=tk.NORMAL)
    else:
        print("No file selected.")

def process_file():
    text_area.insert(tk.END, "Processing...\n")
    t = threading.Thread(target=process_video)
    t.start()

def process_video():
    select_button.config(state=tk.DISABLED)
    process_button.config(state=tk.DISABLED)
    file_path = max(glob.glob("src/*.mp4"), key=os.path.getctime)

    video = VideoFileClip(file_path)
    duration = video.duration

    # Calculate the start and end times for each part
    part_duration = duration / 4
    part_times = [(i * part_duration, (i + 1) * part_duration) for i in range(4)]

    for i, (start, end) in enumerate(part_times):
        part = video.subclip(start, end)
        part.write_videofile(os.path.join("src", f"part{i + 1}.mp4"), codec="libx264", audio_codec="aac")

    video.close()
    print("File split into 4 parts.")
    text_area.insert(tk.END, "File split into 4 parts.")
    select_button.config(state=tk.NORMAL)
    process_button.config(state=tk.NORMAL)

def main():
    global text_area, process_button, select_button

    root = tk.Tk()
    root.title("MP4 File Selector")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width=800
    height=500
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    select_button = tk.Button(root, text="Select MP4 File", command=open_file_dialog)
    select_button.pack(side=tk.LEFT,padx=20, pady=20)

    process_button = tk.Button(root, text="Process File", command=process_file, state=tk.DISABLED)
    process_button.pack(side=tk.LEFT,padx=20, pady=20)

    text_area = tk.Text(root, height=300, width=500)
    text_area.pack(padx=20, pady=(0, 20))

    root.mainloop()

if __name__ == '__main__':
    main()
