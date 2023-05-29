import cv2
import numpy as np
from threading import Thread
import time
import colorsys
import multiprocessing




class VideoPropertiesExtractor:
	# status codes
	DISCONNECTED = 0
	RUNNING = 1
	FINISHED = 2
	ERROR = 3
	CANCELED = 4


	def __init__(self, video_path: str, height: int) -> None:
		"""
		Creates an object for video properties extraction, and initializes its functionality.

		Args:
			video_path (str): The path of the video stream.
			height (int): The height which the video will be resized to.
		"""
		self.status = VideoPropertiesExtractor.RUNNING
		
		self.capture = cv2.VideoCapture(video_path)
		frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

		cap_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
		cap_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
		self.height = height
		self.width = int(height * cap_width / cap_height)

		if not self.capture.isOpened():
			self.status = VideoPropertiesExtractor.ERROR
			print("Error opening video file")
			return
		
		self.prev_frame, self.prev_gray = self.capture_frame()
		self.next_frame, self.next_gray = self.capture_frame()

		# thread constants
		self.n_threads = multiprocessing.cpu_count()
		self.th_length = self.width // self.n_threads
	

	def capture_frame(self) -> tuple:
		"""
		Captures the next video frame, resizes it, and converts it to grayscale

		Return:
			frame: the next resized frame in color
			gray: the next resized frame in grayscale
		"""
		success, frame = self.capture.read()
		frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		if not success:
			self.status = VideoPropertiesExtractor.FINISHED
		return frame, gray
	
	
	def get_values(self) -> tuple:
		"""
		Captures the next video frame, resizes it, and converts it to grayscale

		Return:
			energy: the avergae energy value in the frame
			h: the average hue of the frame
			s: the average saturation of the frame
			v: the average value of the frame
		"""
		n_threads = self.n_threads
		frame = self.next_frame
		gray = self.next_gray

		threads = [None] * n_threads
		energy = [0.0] * n_threads


		for i in range(n_threads):
			threads[i] = Thread(target=self.th_energy, args=(gray, self.prev_gray, self.width, self.th_length, energy, i))
			threads[i].start()

		h, s, v = colorsys.rgb_to_hsv(
			frame[:,:,2].mean()/255.0,
			frame[:,:,1].mean()/255.0,
			frame[:,:,0].mean()/255.0
			)
		self.next_frame, self.next_gray = self.capture_frame()

		for i in range(n_threads):
			threads[i].join()
		
		self.prev_frame = frame
		self.prev_gray = gray

		return np.mean(energy), h, s, v
	

	def th_energy(self, gray, prev_gray, width, length, energy, i):
		"""
		Calculate the energy from the previous frame and the current frame.

		Args:
			gray: The current frame in grayscale.
			prev_gray: The previous frame in grayscale.
			width: The width of the frame.
			length: The amount of columns of the frame to be processed by the thread
			energy: An array of floats where the result will be written in energy[i]
			i: The number of the thread
		"""
		start = length * i
		end = start+length if i != self.n_threads-1 else width-1

		# Calculate optical flow using Lucas-Kanade method
		flow = cv2.calcOpticalFlowFarneback(prev_gray[:,start:end], gray[:,start:end], None, 0.5, 3, 15, 3, 5, 1.2, 0)
		# Calculate the energy as the average of the magnitude of the flow vectors
		energy[i] = np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2))




# class to time specific parts of the code
class ComponentTimer():
	def __init__(self) -> None:
		self.component = {}
		self.start_time = {}
	

	def start(self, component = "__default__") -> None:
		self.start_time[component] = time.time_ns()


	def time(self, component = "__default__") -> None:
		new_ts = time.time_ns()
		if component in self.component.keys():
			self.component[component] += new_ts - self.start_time[component]
		else:
			self.component[component] = new_ts - self.start_time[component]


	def get_all_components(self) -> dict:
		return self.component


	def get(self, component = "__default__") -> int:
		return self.component[component]

	def get_sum(self) -> int:
		sum = 0
		for _, v in self.component.items():
			sum += v
		return sum




if __name__ == "__main__":

	paths = [
		'example_videos/v1.mp4',
		'example_videos/v2.mp4',
		'example_videos/v3.mp4',
		'example_videos/v4.mp4',
		'example_videos/v5.mp4',
		'example_videos/v6.mp4',
		'example_videos/v7.mp4',
		]
	n_frames = 100

	for path in paths:
		print(f"\n***** Calculating {n_frames} frames of video '{path}' *****")
		video_extractor = VideoPropertiesExtractor(path, 180)
		
		frames = []
		lenergy = []
		lhue = []
		lsaturation = []
		lbrightness = []

		ctimer = ComponentTimer()

		i_frames = 0
		while video_extractor.status == VideoPropertiesExtractor.RUNNING and i_frames < 100:
			ctimer.start("get_values")
			values = video_extractor.get_values()
			ctimer.time("get_values")

			if values is not None:
				i_frames += 1
				ctimer.start("main_if")
				#frame_num, energy, hue, saturation, brightness = values
				energy, hue, saturation, brightness = values
				frames.append({
					"energy": energy,
					"hue": hue,
					"saturation": saturation,
					"brightness": brightness})
				lenergy.append(energy)
				lhue.append(hue)
				lsaturation.append(saturation)
				lbrightness.append(brightness)

				#print(f"Frame {i_frames}: Energy={energy}, HUE={hue}, Saturation={saturation}, Brightness={brightness}")
				ctimer.time("main_if")

		print(ctimer.get_all_components())
		print(f"Took {(ctimer.get_sum())/1000000000.0} seconds.")

		#with open(path + ".txt", mode="wt") as f:
		#	f.write(str(frames))

		print("mean", np.mean(lenergy), np.mean(lhue), np.mean(lsaturation), np.mean(lbrightness))
		print("max", max(lenergy), max(lhue), max(lsaturation), max(lbrightness))

		

