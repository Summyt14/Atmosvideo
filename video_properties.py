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

    def start_extracting(self, video_path: str, width: int, num_threads: int):
        """
        Start extracting properties from the video.

        Args:
            video_path (str): The path of the video stream.
            width (int): The width which the video will be resized to.
            num_threads (int): The number of threads that will work simultaneously on the extractor.
        """
        self.status = RUNNING
        self.thread = threading.Thread(target=self.run_extractor, args=(video_path, width, num_threads))
        self.thread.start()

    def run_extractor(self, video_path: str, width: int, num_threads: int):
        """
        Runs the thread for capturing and processing frames from the video.

        Args:
            video_path (str): The path of the video stream.
            width (int): The width which the video will be resized to.
        """
        capture = cv2.VideoCapture(video_path)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        new_height = int(width * cap_height / cap_width)

        if not capture.isOpened():
            self.status = ERROR
            print("Error opening video file")
            return
        
        _, frame = capture.read()
        frame = cv2.resize(frame, (width, new_height), interpolation=cv2.INTER_AREA)

        frame_queue = queue.Queue()
        for frame_index in range(frame_count):
            frame_queue.put(frame_index)

        threads = []
        lock = threading.Lock()
        for _ in range(num_threads):
            threads.append(threading.Thread(target=self.worker, args=(capture, frame, frame_queue, width, new_height, lock)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.status = FINISHED
        capture.release()

    def worker(self, capture, prev_frame, frame_queue: queue.Queue, width: int, height: int, lock: threading.Lock):
        """
        Creates a thread and extracts information from the next available frame in the queue.

        Args:
            capture: The video stream.
            prev_frame: The previous frame.
            frame_queue (Queue): The queue of frames to be extracted.
            width (int): The width to scale the frame.
            height (int): The height to scale the frame.
            lock (Lock): The lock to allow only one access at a time to the capture.
        """
        while True:
            try:
                frame_index = frame_queue.get(block=False)
            except queue.Empty:
                break

            with lock:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()

            if not success:
                break
            
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            self.extract_properties(frame, prev_frame, frame_index)
            prev_frame = frame

    def extract_properties(self, frame, prev_frame, frame_index: int):
        """
        Extract the properties from the current frame.

        Args:
            prev_frame: The previous frame.
            frame: The current frame.
        """
        energy = self.calculate_energy(frame, prev_frame)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Extract HUE, saturation, and brightness
        # hue: 0-179
        # saturation: 0-255
        # brightness: 0-255
        hue = hsv[:,:,0].mean()
        saturation = hsv[:,:,1].mean()
        brightness = hsv[:,:,2].mean()

        with threading.Lock():
            self.queue.put((frame_index, energy, hue, saturation, brightness))

    def calculate_energy(self, frame, prev_frame):
        """
        Calculate the energy from the previous frame and the current frame.

        Args:
            frame: The current frame.
            prev_frame: The previous frame.
        """
        # Convert frames to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        # Calculate optical flow using Lucas-Kanade method
        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        # Calculate the energy as the sum of squared magnitudes of the flow vectors
        energy = np.sum(flow[..., 0]**2 + flow[..., 1]**2)
        return energy
    
    
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
    video_extractor.start_extracting(path, 320, 4)

    while video_extractor.status == RUNNING:
        values = video_extractor.get_values()
        if values is not None:
            frame_num, energy, hue, saturation, brightness = values
            print(f"Frame {frame_num}: Energy={energy}, HUE={hue}, Saturation={saturation}, Brightness={brightness}")
