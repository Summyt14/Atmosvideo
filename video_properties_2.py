import cv2
import numpy as np
from threading import Thread
import time
import colorsys
import multiprocessing
from pprint import pprint




class VideoPropertiesExtractor:
	# status codes
	DISCONNECTED = 0
	RUNNING = 1
	FINISHED = 2
	ERROR = 3
	CANCELED = 4


	def __init__(self, height:int = 180) -> None:
		"""
		Creates an object for video properties extraction, and initializes its functionality.

		Args:
			video_path (str): The path of the video stream.
			height (int): The height which the video will be resized to.
		"""
		self.status = VideoPropertiesExtractor.DISCONNECTED
		self.capture = None
		self.frame_count = 0
		self.height = height
		self.width = 0
		self.prev_frame = None
		self.next_frame = None
		self.prev_gray = None
		self.next_gray = None
		self.n_threads = multiprocessing.cpu_count()
		#self.timer = ComponentTimer()
		#self.th_length = self.width // self.n_threads
	
	def load(self, video_path:str) -> None:
		self.status = VideoPropertiesExtractor.RUNNING
		
		self.capture = cv2.VideoCapture(video_path)
		if not self.capture.isOpened():
			self.status = VideoPropertiesExtractor.ERROR
			print("Error opening video file")
			return
		
		self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
		self.fps = self.capture.get(cv2.CAP_PROP_FPS)
		cap_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
		cap_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
		self.width = int(self.height * cap_width / cap_height)

		
		self.capture_frame()
		self.prev_frame = self.next_frame
		self.prev_gray = self.next_gray
		self.capture_frame()

		# thread constants
		self.th_length = self.width // self.n_threads
		
	

	def capture_frame(self) -> bool:
		"""
		Captures the next video frame, resizes it, and converts it to grayscale

		Return:
			frame: the next resized frame in color
			gray: the next resized frame in grayscale
		"""
		success, frame = self.capture.read()
		if not success:
			self.status = VideoPropertiesExtractor.FINISHED
			return False
		self.next_frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
		self.next_gray = cv2.cvtColor(self.next_frame, cv2.COLOR_BGR2GRAY)
		#print(f"Capture: w({len(self.next_gray[0])}), h({len(self.next_gray)})")
		return True
	
	
	def step(self) -> bool:
		"""
		Captures the next video frame, resizes it, and converts it to grayscale

		Return:
			energy: the avergae energy value in the frame
			h: the average hue of the frame
			s: the average saturation of the frame
			v: the average value of the frame
		"""
		if self.status != VideoPropertiesExtractor.RUNNING:
			return None
		
		n_threads = self.n_threads
		frame = self.next_frame
		gray = self.next_gray

		threads = [None] * n_threads
		energy = [0.0] * n_threads

		#self.timer.start("th_create")
		for i in range(n_threads):
			threads[i] = Thread(target=self.th_energy, args=(gray, self.prev_gray, self.width, self.th_length, energy, i))
			threads[i].start()
		#self.timer.time("th_create")
		#self.timer.start("th_main")

		h, s, v = colorsys.rgb_to_hsv(
			frame[:,:,2].mean()/255.0,
			frame[:,:,1].mean()/255.0,
			frame[:,:,0].mean()/255.0
			)
		self.capture_frame()

		self.prev_frame = frame
		self.prev_gray = gray

		#self.timer.time("th_main")
		#self.timer.start("join")
		for i in range(n_threads):
			threads[i].join()
		#self.timer.time("join")
		

		self.values = min(np.mean(energy) * 1.2, 1.0), h, s, v

		return self.status == VideoPropertiesExtractor.RUNNING
	

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
		#name = "th" + str(i)
		#self.timer.start(name)
		start = length * i
		end = start+length if i != self.n_threads-1 else width-1

		# Calculate optical flow using Lucas-Kanade method
		flow = cv2.calcOpticalFlowFarneback(prev_gray[:,start:end], gray[:,start:end], None, 0.5, 3, 15, 3, 5, 1.2, 0)
		# Calculate the energy as the average of the magnitude of the flow vectors
		energy[i] = np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2))
		#energy[i] = np.mean(abs(flow[..., 0]) + abs(flow[..., 1]))
		#self.timer.time(name)





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

	video_extractor = VideoPropertiesExtractor(180)
	for path in paths:
		print(f"\n***** Calculating frames of video '{path}' *****")
		video_extractor.load(path)
		
		frames = []
		lenergy = []
		lhue = []
		lsaturation = []
		lbrightness = []

		ctimer = ComponentTimer()
		video_extractor.timer = ctimer

		running = True
		i_frame = 0
		while running:
			i_frame += 1
			ctimer.start("get_values")
			running = video_extractor.step()
			e, h, s, v = video_extractor.values
			ctimer.time("get_values")

			lenergy.append(e)
			lhue.append(h)
			lsaturation.append(s)
			lbrightness.append(v)

			print(f"Frame {i_frame}: Energy: {e}, Hue: {h}, Saturation: {s}, Value: {v}")

		#print(ctimer.get_all_components())
		pprint(ctimer.get_all_components())
		print(f"Took {ctimer.get('get_values')/1000000000.0} seconds for {i_frame} frames ({i_frame*1000000000.0/ctimer.get('get_values')} fps).")

		#with open(path + ".txt", mode="wt") as f:
		#	f.write(str(frames))

		print("mean", np.mean(lenergy), np.mean(lhue), np.mean(lsaturation), np.mean(lbrightness))
		print("max", max(lenergy), max(lhue), max(lsaturation), max(lbrightness))

		

