import customtkinter
import os
import datetime
import vlc
import cv2
import shutil
import threading
from PIL import Image


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAILS_DIR = os.path.join(CURRENT_DIR, 'thumbnails')
VIDEOS_DIR = os.path.join(CURRENT_DIR, 'example_videos')
IMAGES_DIR = os.path.join(CURRENT_DIR, 'images')


class ScrollableLabelButtonFrame(customtkinter.CTkScrollableFrame):
    def __init__(self, master, command, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.command = command
        self.radiobutton_variable = customtkinter.StringVar()
        self.label_list = []
        self.button_list = []

        mp4_files = []

        for root, dirs, files in os.walk(VIDEOS_DIR):
            for filename in files:
                if filename.endswith('.mp4'):
                    mp4_files.append(os.path.join(root, filename))
                    image_name = f"{os.path.splitext(filename)[0]}.jpg"
                    self.add_item(os.path.join(root, filename), thumbnail=customtkinter.CTkImage(Image.open(os.path.join(THUMBNAILS_DIR, image_name)), size=(128, 72)))

    def add_item(self, video_path, thumbnail):
        filename = os.path.basename(video_path)
        label = customtkinter.CTkLabel(self, text=filename.split('.')[0], image=thumbnail, compound="left", padx=10, anchor="w", wraplength=150, justify="left")
        button = customtkinter.CTkButton(self, text="Play", width=50, height=35)
        button.configure(command=lambda: self.command(video_path))
        label.grid(row=len(self.label_list), column=0, pady=(0, 10), sticky="w")
        button.grid(row=len(self.button_list), column=1, pady=(0, 10), padx=5)
        self.label_list.append(label)
        self.button_list.append(button)

    def remove_item(self, item):
        for label, button in zip(self.label_list, self.button_list):
            if item == label.cget("text"):
                label.destroy()
                button.destroy()
                self.label_list.remove(label)
                self.button_list.remove(button)
                return
            
class PlayerControlsFrame(customtkinter.CTkFrame):
    def __init__(self, master, vlc_instance: vlc.Instance, video_player: vlc.MediaPlayer, saved_video_event, **kwargs):
        super().__init__(master, **kwargs)

        self.vlc_instance = vlc_instance
        self.video_player = video_player
        self.saved_video_event = saved_video_event
        self.video_path = ""
        self.last_volume = 100

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.rewind_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "rewind.png")))
        self.play_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "pause.png")))
        self.fast_forward_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "fast-forward.png")))
        self.volume_on_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "high-volume.png")))
        self.volume_off_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "mute.png")))
        self.generate_image = customtkinter.CTkImage(Image.open(os.path.join(IMAGES_DIR, "generate.png")))

        self.slider_frame = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.start_time_label = customtkinter.CTkLabel(master=self.slider_frame, text=str(datetime.timedelta(seconds=0)))
        self.progress_value = customtkinter.IntVar(master=self.slider_frame)
        self.progress_slider = customtkinter.CTkSlider(master=self.slider_frame, width=550, variable=self.progress_value, from_=0, to=1, orientation="horizontal", command=self.seek)
        self.end_time_label = customtkinter.CTkLabel(master=self.slider_frame, text=str(datetime.timedelta(seconds=0)))
        self.slider_frame.grid_columnconfigure(0, weight=1)
        self.slider_frame.grid_columnconfigure(1, weight=4)
        self.slider_frame.grid_columnconfigure(2, weight=1)
        self.slider_frame.grid(row=0, column=0, padx=0, pady=0, sticky="NEW")

        self.buttons_frame = customtkinter.CTkFrame(master=self, corner_radius=0)
        self.button_browse = customtkinter.CTkButton(master=self.buttons_frame, width=50, height=30, text="Browse Video", command=self.browse)
        self.button_save = customtkinter.CTkButton(master=self.buttons_frame, width=50, height=30, text="Save", command=self.save_video)
        self.button_rewind = customtkinter.CTkButton(master=self.buttons_frame, image=self.rewind_image, text="", height=30, width=30, command=lambda: self.skip(-5))
        self.button_play = customtkinter.CTkButton(master=self.buttons_frame, image=self.play_image, text="", height=30, width=30, command=self.play_pause)
        self.button_fast_forward = customtkinter.CTkButton(master=self.buttons_frame, image=self.fast_forward_image, text="", height=30, width=30, command=lambda: self.skip(5))
        self.button_generate = customtkinter.CTkButton(master=self.buttons_frame, image=self.generate_image, text="", height=30, width=30, command=lambda: self.generate)

        self.volume_frame = customtkinter.CTkFrame(master=self.buttons_frame, fg_color="transparent")
        self.button_volume = customtkinter.CTkButton(master=self.volume_frame, image=self.volume_on_image, text="", height=30, width=30, command=lambda: self.volume_on_off())
        self.volume_value = customtkinter.IntVar(master=self.volume_frame)
        self.volume_slider = customtkinter.CTkSlider(master=self.volume_frame, width=100, variable=self.volume_value, from_=0, to=100, orientation="horizontal", command=self.set_volume_throttled)
        self.volume_slider.set(100)
        self.volume_update_delay = 500  # Delay in milliseconds between volume updates
        self.volume_update_pending = False  # Flag to track pending volume updates
        self.volume_update_timer = None

        self.buttons_frame.grid(row=1, column=0, padx=0, pady=0, sticky="NEW")
        self.start_time_label.grid(row=0, column=0, padx=10, pady=10)
        self.progress_slider.grid(row=0, column=1, padx=10, pady=10)
        self.end_time_label.grid(row=0, column=2, padx=10, pady=10)
        self.button_browse.grid(row=0, column=0, padx=10, pady=10)
        self.button_save.grid(row=0, column=1, padx=10, pady=10)
        self.button_rewind.grid(row=0, column=2, padx=10, pady=10)
        self.button_play.grid(row=0, column=3, padx=10, pady=10)
        self.button_fast_forward.grid(row=0, column=4, padx=10, pady=10)
        self.volume_frame.grid(row=0, column=5, padx=0, pady=10)
        self.button_generate.grid(row=0, column=6, padx=10, pady=10)
        self.button_volume.grid(row=0, column=0, padx=10, pady=10)

        self.volume_frame.bind("<Enter>", self.show_volume_slider)
        self.volume_frame.bind("<Leave>", self.hide_volume_slider)
        self.volume_slider.bind("<Enter>", self.show_volume_slider)
        self.button_volume.bind("<Enter>", self.show_volume_slider)
        self.video_player.event_manager().event_attach(vlc.EventType.MediaPlayerTimeChanged, self.update_current_time)
        self.video_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.video_ended)

    def update_current_time(self, event):
        duration = self.video_player.get_length()
        self.start_time_label.configure(text=str(datetime.timedelta(milliseconds=self.video_player.get_time()))[:-3].split(".", 1)[0])
        self.end_time_label.configure(text=str(datetime.timedelta(milliseconds=duration))[:-3].split(".", 1)[0])
        self.progress_slider.configure(to=duration)
        self.progress_value.set(int(self.video_player.get_time()))

    def video_ended(self, event):
        self.progress_slider.set(0)
        self.start_time_label.configure(text=str(datetime.timedelta(seconds=0)))
        restart_thread = threading.Thread(target=self.restart_video)
        restart_thread.start()

    def restart_video(self):
        self.video_player.stop()
        self.video_player.set_time(0)

    def volume_on_off(self):
        if self.video_player.audio_get_volume() > 0:
            self.volume_value.set(0)
            self.button_volume.configure(image=self.volume_off_image)
        else:
            if self.last_volume == 0:
                self.last_volume = 100
            self.volume_value.set(self.last_volume)
            self.button_volume.configure(image=self.volume_on_image)
        self.video_player.audio_set_volume(int(self.volume_value.get()))

    def set_volume_throttled(self, volume):
        if not self.volume_update_pending:
            self.volume_update_pending = True
            self.after(self.volume_update_delay, self.update_volume)

    def update_volume(self):
        new_volume = int(self.volume_value.get())
        if new_volume > 0:
            self.button_volume.configure(image=self.volume_on_image)
        else:
            self.button_volume.configure(image=self.volume_off_image)
        self.last_volume = new_volume
        self.video_player.audio_set_volume(new_volume)
        self.volume_update_pending = False

    def seek(self, value):
        if self.video_path == "":
            return
        if not self.video_player.is_playing():
            self.video_player.play()
            self.video_player.set_time(int(value))
        else:
            self.video_player.set_time(int(value))

    def skip(self, value):
        if self.video_path == "":
            return
        if not self.video_player.is_playing():
            self.video_player.play()
        current_time = self.video_player.get_time()
        new_time = current_time + (value * 1000)
        self.video_player.set_time(new_time)

    def browse(self, video_path=None):
        if video_path:
            self.video_path = video_path
        else:
            self.video_path = customtkinter.filedialog.askopenfilename()
        if self.video_path:
            media = self.vlc_instance.media_new(self.video_path)
            self.video_player.set_media(media)
            self.progress_slider.configure(from_=0, to=1)
            self.progress_value.set(0)

    def play_pause(self):
        if self.video_path == "":
            return
        if self.video_player.is_playing():
            self.video_player.pause()
        else:
            self.video_player.play()

    def save_video(self):
        if not os.path.exists(VIDEOS_DIR):
            os.makedirs(VIDEOS_DIR)
        
        if self.video_path == "":
            return
        filename = os.path.basename(self.video_path)
        destination_file_path = os.path.join(VIDEOS_DIR, filename)
        shutil.copyfile(self.video_path, destination_file_path)
        print(f"File copied to: {destination_file_path}")

        self.create_thumbnail(self.video_path)
        self.saved_video_event(self.video_path)

    def create_thumbnail(self, video_path):
        if not os.path.exists(THUMBNAILS_DIR):
            os.makedirs(THUMBNAILS_DIR)

        filename = os.path.basename(video_path)
        if filename.endswith('.mp4'):
            thumbnail_path = os.path.join(THUMBNAILS_DIR, f"{os.path.splitext(filename)[0]}.jpg")
            video_capture = cv2.VideoCapture(video_path)
            success, frame = video_capture.read()
            if success:
                cv2.imwrite(thumbnail_path, frame)
                print(f"Thumbnail saved for {filename}")
            else:
                print(f"Failed to extract thumbnail for {filename}")
            video_capture.release()

    def show_volume_slider(self, event):
        self.volume_slider.grid(row=0, column=1, padx=10, pady=10)

    def hide_volume_slider(self, event):
        if event.widget != self.volume_slider and event.widget != self.button_volume and event.widget != self.volume_frame:
            self.volume_slider.grid_forget()

    def generate(self):
        if self.video_path != "":
            #TODO generate music
            pass


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Atmosvideo")
        self.geometry(f"{1100}x{580}")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.player_frame = customtkinter.CTkFrame(master=self, corner_radius=0, fg_color="transparent")
        self.player_frame.grid_rowconfigure(0, weight=3)
        self.player_frame.grid_rowconfigure(1, weight=1)
        self.player_frame.grid_columnconfigure(0, weight=1)
        self.player_frame.grid(row=0, column=0, padx=10, pady=10, sticky="NSEW")

        self.vlc_instance = vlc.Instance()
        self.video_player = self.vlc_instance.media_player_new()
        self.player_frame_video_player = customtkinter.CTkFrame(master=self.player_frame)
        self.player_frame_video_player.grid(row=0, column=0, padx=0, pady=0, sticky="NSEW")

        self.controls_frame = PlayerControlsFrame(master=self.player_frame, vlc_instance=self.vlc_instance, video_player=self.video_player, saved_video_event=self.saved_video_event, corner_radius=0, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, padx=0, pady=0, sticky="NEW")
        
        self.scrollable_label_button_frame = ScrollableLabelButtonFrame(master=self, width=350, command=self.label_button_frame_event)
        self.scrollable_label_button_frame.grid(row=0, column=1, padx=0, pady=10, sticky="nsew")
           

    def label_button_frame_event(self, video_path):
        self.controls_frame.browse(video_path)
        self.controls_frame.play_pause()

    def saved_video_event(self, video_path):
        filename = os.path.basename(video_path)
        image_name = f"{os.path.splitext(filename)[0]}.jpg"
        self.scrollable_label_button_frame.add_item(video_path, thumbnail=customtkinter.CTkImage(Image.open(os.path.join(THUMBNAILS_DIR, image_name)), size=(128, 72)))

    def run(self):
        self.video_player.set_hwnd(self.player_frame_video_player.winfo_id())
        self.mainloop()


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    app = App()
    app.run()