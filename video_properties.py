import cv2
import numpy as np
import threading
import queue

DISCONNECTED = 0
RUNNING = 1
FINISHED = 2
ERROR = 3
CANCELED = 4


class ExtractVideoProperties:
    """
    A class that handles the extraction of video properties.
    """
    def __init__(self) -> None:
        self.status = DISCONNECTED
        self.thread = None
        self.lock = threading.Lock()
        self.queue = queue.Queue()

    def start_extracting(self, video_path: str):
        """
        Start extracting properties from the video.

        Args:
            video_path (str): The path of the video stream.
        """
        self.status = RUNNING
        self.thread = threading.Thread(target=self.run_thread, args=(video_path,))
        self.thread.start()

    def run_thread(self, video_path: str):
        """
        Runs the thread for capturing and processing frames from the video.

        Args:
            video_path (str): The path of the video stream.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.status = ERROR
            print("Error opening video file")
            return

        self.lock.acquire()
        ret, frame = cap.read()
        prev_frame = frame
        frame_num = 0

        while self.status == RUNNING:
            if not ret or self.status == DISCONNECTED or self.status == ERROR:
                print("Error reading the frames of the video")
                self.status = ERROR

            energy = self.calculate_energy(frame, prev_frame)

            # Convert frame to HSV color space
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Extract HUE, saturation, and brightness
            # hue: 0-179
            # saturation: 0-255
            # brightness: 0-255
            hue = hsv[:,:,0].mean()
            saturation = hsv[:,:,1].mean()
            brightness = hsv[:,:,2].mean()
            self.queue.put((frame_num, energy, hue, saturation, brightness))

            prev_frame = frame
            frame_num += 1
            ret, frame = cap.read()
            # Break the loop if no more frames
            if not ret:
                self.status = FINISHED

        cap.release()
        self.lock.release()

    def calculate_energy(self, frame, prev_frame):
        """
        Calculate the energy from the previous frame and the current frame.

        Args:
            frame: The current frame
            prev_frame: The previous frame
        """
        # Convert frames to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        # Calculate optical flow using Lucas-Kanade method
        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        # Calculate the energy as the sum of squared magnitudes of the flow vectors
        energy = np.sum(flow[..., 0]**2 + flow[..., 1]**2)
        return energy
    
    def shutdown(self) -> None:
        """
        Shutdowns the properties extractor.
        """
        self.lock.acquire()
        self.status = CANCELED
        self.lock.release()
        self.thread.join()

    def get_values(self) -> None:
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
    path = 'example_videos/v4.mp4'
    video_extractor = ExtractVideoProperties()
    video_extractor.start_extracting(path)
    while video_extractor.status == RUNNING:
        values = video_extractor.get_values()
        if values is not None:
            frame_num, energy, hue, saturation, brightness = values
            print(f"Frame {frame_num}: Energy={energy}, HUE={hue}, Saturation={saturation}, Brightness={brightness}")
