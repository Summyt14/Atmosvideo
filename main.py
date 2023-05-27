import customtkinter
import os
import datetime
import vlc
from PIL import Image


class ScrollableLabelButtonFrame(customtkinter.CTkScrollableFrame):
    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.command = command
        self.radiobutton_variable = customtkinter.StringVar()
        self.label_list = []
        self.button_list = []

    def add_item(self, item, image=None):
        label = customtkinter.CTkLabel(self, text=item, image=image, compound="left", padx=5, anchor="w")
        button = customtkinter.CTkButton(self, text="Command", width=100, height=24)
        if self.command is not None:
            button.configure(command=lambda: self.command(item))
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
    def __init__(self, master, vlc_instance: vlc.Instance, video_player: vlc.MediaPlayer, **kwargs):
        super().__init__(master, **kwargs)

        self.vlc_instance = vlc_instance
        self.video_player = video_player
        self.video_path = ""
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        rewind_image = customtkinter.CTkImage(Image.open(os.path.join(self.current_dir, "images", "rewind.png")))
        play_image = customtkinter.CTkImage(Image.open(os.path.join(self.current_dir, "images", "pause.png")))
        fast_forward_image = customtkinter.CTkImage(Image.open(os.path.join(self.current_dir, "images", "fast-forward.png")))

        self.slider_frame = customtkinter.CTkFrame(master=self)
        self.start_time_label = customtkinter.CTkLabel(master=self.slider_frame, text=str(datetime.timedelta(seconds=0)))
        self.progress_value = customtkinter.IntVar(master=self.slider_frame)
        self.progress_slider = customtkinter.CTkSlider(master=self.slider_frame, width=550, variable=self.progress_value, from_=0, to=1, orientation="horizontal", command=self.seek)
        self.end_time_label = customtkinter.CTkLabel(master=self.slider_frame, text=str(datetime.timedelta(seconds=0)))
        self.slider_frame.grid_columnconfigure(0, weight=1)
        self.slider_frame.grid_columnconfigure(1, weight=4)
        self.slider_frame.grid_columnconfigure(2, weight=1)
        self.slider_frame.grid(row=0, column=0, padx=0, pady=0, sticky="NEW")

        self.buttons_frame = customtkinter.CTkFrame(master=self)
        self.button_browse = customtkinter.CTkButton(master=self.buttons_frame, height=30, text="Browse Video", command=self.browse)
        self.button_rewind = customtkinter.CTkButton(master=self.buttons_frame, image=rewind_image, text="", height=30, width=30, command=lambda: self.skip(-5))
        self.button_play = customtkinter.CTkButton(master=self.buttons_frame, image=play_image, text="", height=30, width=30, command=self.play_pause)
        self.button_fast_forward = customtkinter.CTkButton(master=self.buttons_frame, image=fast_forward_image, text="", height=30, width=30, command=lambda: self.skip(5))
        self.volume_value = customtkinter.IntVar(master=self.buttons_frame)
        self.volume_slider = customtkinter.CTkSlider(master=self.buttons_frame, width=100, variable=self.volume_value, from_=0, to=100, orientation="horizontal", command=self.set_volume_throttled)
        self.volume_slider.set(100)
        self.volume_update_delay = 500  # Delay in milliseconds between volume updates
        self.volume_update_pending = False  # Flag to track pending volume updates
        self.volume_update_timer = None
        self.buttons_frame.grid(row=1, column=0, padx=0, pady=0, sticky="NEW")

        self.start_time_label.grid(row=0, column=0, padx=10, pady=10)
        self.progress_slider.grid(row=0, column=1, padx=10, pady=10)
        self.end_time_label.grid(row=0, column=2, padx=10, pady=10)

        self.button_browse.grid(row=0, column=0, padx=10, pady=10)
        self.button_rewind.grid(row=0, column=1, padx=10, pady=10)
        self.button_play.grid(row=0, column=2, padx=10, pady=10)
        self.button_fast_forward.grid(row=0, column=3, padx=10, pady=10)
        self.volume_slider.grid(row=0, column=4, padx=10, pady=10)

        self.video_player.event_manager().event_attach(vlc.EventType.MediaPlayerTimeChanged, self.update_current_time)
        self.video_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.video_ended)

    def update_current_time(self, event):
        duration = self.video_player.get_length()
        self.start_time_label.configure(text=str(datetime.timedelta(milliseconds=self.video_player.get_time()))[:-3].split(".", 1)[0])
        self.end_time_label.configure(text=str(datetime.timedelta(milliseconds=duration))[:-3].split(".", 1)[0])
        self.progress_slider.configure(to=duration)
        self.progress_value.set(int(self.video_player.get_time()))

    def set_volume_throttled(self, volume):
        if not self.volume_update_pending:
            self.volume_update_pending = True
            self.after(self.volume_update_delay, self.update_volume)

    def update_volume(self):
        self.video_player.audio_set_volume(int(self.volume_value.get()))
        self.volume_update_pending = False

    def seek(self, value):
        if self.video_path == "":
            return
        self.video_player.set_time(int(value))

    def skip(self, value):
        if self.video_path == "":
            return
        current_time = self.video_player.get_time()
        new_time = current_time + (value * 1000)
        self.video_player.set_time(new_time)

    def video_ended(self, event):
        self.progress_slider.set(0)
        self.start_time_label.configure(text=str(datetime.timedelta(seconds=0)))

    def browse(self):
        self.video_path = customtkinter.filedialog.askopenfilename()
        if self.video_path:
            media = self.vlc_instance.media_new(self.video_path)
            self.video_player.set_media(media)
            self.progress_slider.configure(from_=0, to=1)
            self.progress_value.set(0)

    def play_pause(self):
        if self.video_path == "":
            return
        if self.video_player.can_pause():
            self.video_player.pause()
        else:
            self.video_player.play()


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Atmosvideo")
        self.geometry(f"{1100}x{580}")
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

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

        self.controls_frame = PlayerControlsFrame(master=self.player_frame, vlc_instance=self.vlc_instance, video_player=self.video_player, corner_radius=0, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, padx=0, pady=0, sticky="NEW")
        
        self.scrollable_label_button_frame = ScrollableLabelButtonFrame(master=self, width=350, command=self.label_button_frame_event, corner_radius=0)
        self.scrollable_label_button_frame.grid(row=0, column=1, padx=0, pady=10, sticky="nsew")
        for i in range(5):
            self.scrollable_label_button_frame.add_item(f"image and item {i}", image=customtkinter.CTkImage(Image.open(os.path.join(self.current_dir, "images", "chat_light.png"))))

    def label_button_frame_event(self, item):
        print(f"label button frame clicked: {item}")

    def run(self):
        self.video_player.set_hwnd(self.player_frame_video_player.winfo_id())
        self.mainloop()


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    app = App()
    app.run()