import cv2
import numpy as np
import threading
import queue
import matplotlib.pyplot as plt

DISCONNECTED = 0
RUNNING = 1
FINISHED = 2
ERROR = 3
CANCELED = 4


class ExtractVideoProperties:
    """
    A class that handles the extraction of video properties.
    """
    def __init__(self):
        self.status = DISCONNECTED
        self.thread = None
        self.lock = threading.Lock()
        self.queue = queue.Queue()

    def start_extracting(self, video_path: str, width: int, do_plot: bool = False):
        """
        Start extracting properties from the video.

        Args:
            video_path (str): The path of the video stream.
            width (int): The width which the video will be resized to.
            do_plot: Show the movement flow image.
        """
        self.status = RUNNING
        self.thread = threading.Thread(target=self.run_thread, args=(video_path, width, do_plot))
        self.thread.start()

    def run_thread(self, video_path: str, width: int, do_plot: bool):
        """
        Runs the thread for capturing and processing frames from the video.

        Args:
            video_path (str): The path of the video stream.
            width (int): The width which the video will be resized to.
            do_plot: Show the movement flow image.
        """
        cap = cv2.VideoCapture(video_path)
        cap_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        new_height = int(width * cap_height / cap_width)

        if not cap.isOpened():
            self.status = ERROR
            print("Error opening video file")
            return

        self.lock.acquire()
        ret, frame = cap.read()
        frame = cv2.resize(frame, (width, new_height), interpolation=cv2.INTER_AREA)
        prev_frame = frame
        frame_num = 0

        while self.status == RUNNING:
            if not ret or self.status == DISCONNECTED or self.status == ERROR:
                print("Error reading the frames of the video")
                self.status = ERROR

            energy, plot = self.calculate_energy(frame, prev_frame, do_plot)

            # Convert frame to HSV color space
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Extract HUE, saturation, and brightness
            # hue: 0-179
            # saturation: 0-255
            # brightness: 0-255
            hue = hsv[:,:,0].mean()
            saturation = hsv[:,:,1].mean()
            brightness = hsv[:,:,2].mean()
            self.queue.put((frame_num, energy, hue, saturation, brightness, plot))

            prev_frame = frame
            frame_num += 1
            ret, frame = cap.read()
            frame = cv2.resize(frame, (width, new_height), interpolation=cv2.INTER_AREA)

            # Break the loop if no more frames
            if not ret:
                self.status = FINISHED

        cap.release()
        self.lock.release()

    def calculate_energy(self, frame, prev_frame, do_plot):
        """
        Calculate the energy from the previous frame and the current frame.

        Args:
            frame: The current frame.
            prev_frame: The previous frame.
            do_plot: Show the movement flow image.
        """
        # Convert frames to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        # Calculate optical flow using Lucas-Kanade method
        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        # Calculate the energy as the sum of squared magnitudes of the flow vectors
        energy = np.sum(flow[..., 0]**2 + flow[..., 1]**2)
        plot = None

        if do_plot:
            magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])

            # Create an RGB image to visualize the flow
            hsv1 = np.zeros_like(prev_frame)
            hsv1[..., 1] = 255
            hsv1[..., 0] = angle * 180 / np.pi / 2
            hsv1[..., 2] = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX)
            plot = cv2.cvtColor(hsv1, cv2.COLOR_HSV2BGR)

        return energy, plot
    
    def shutdown(self):
        """
        Shutdowns the properties extractor.
        """
        self.lock.acquire()
        self.status = CANCELED
        self.lock.release()
        self.thread.join()

    def get_values(self):
      """
      Retrieves the values of frame_num, energy, hue, saturation, and brightness from the queue.
      Returns:
          A tuple containing the values of frame_num, energy, hue, saturation, and brightness.
      """
      try:
          values = self.queue.get(block=False)
          return values
      except queue.Empty:
          return None


if __name__ == "__main__":
    path = 'example_videos/v1.mp4'
    video_extractor = ExtractVideoProperties()
    video_extractor.start_extracting(path, 320)
    while video_extractor.status == RUNNING:
        values = video_extractor.get_values()
        if values is not None:
            frame_num, energy, hue, saturation, brightness, plot = values
            if plot is not None:
                plt.imshow(plot)
                plt.pause(0.001)
            print(f"Frame {frame_num}: Energy={energy}, HUE={hue}, Saturation={saturation}, Brightness={brightness}")
