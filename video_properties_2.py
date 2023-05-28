from collections.abc import Callable, Iterable, Mapping
from typing import Any
import cv2
import numpy as np
import threading
import queue
from MusicGeneration import MusicGenerator

from threading import Thread
import time
import colorsys
import multiprocessing

DISCONNECTED = 0
RUNNING = 1
FINISHED = 2
ERROR = 3
CANCELED = 4





class ExctractVideoProperties:
	def __init__(self, video_path: str, height: int) -> None:
		"""
		Runs the thread for capturing and processing frames from the video.

		Args:
			video_path (str): The path of the video stream.
			height (int): The height which the video will be resized to.
		"""
		self.timer = ComponentTimer()
		self.status = RUNNING
		
		self.capture = cv2.VideoCapture(video_path)
		frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

		cap_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
		cap_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
		self.height = height
		self.width = int(height * cap_width / cap_height)
		self.n_pixels = height * self.width

		if not self.capture.isOpened():
			self.status = ERROR
			print("Error opening video file")
			return
		
		self.prev_frame, self.prev_gray = self.capture_frame()
		self.next_frame, self.next_gray = self.capture_frame()

		# thread constants
		self.n_threads = multiprocessing.cpu_count()
		self.th_length = self.width // self.n_threads
		self.times = {}
	

	def capture_frame(self):
		success, frame = self.capture.read()
		#frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		if not success:
			self.status = FINISHED
		return frame, gray
	
	
	def get_values(self) -> tuple:
		n_threads = self.n_threads
		frame = self.next_frame
		gray = self.next_gray

		threads = [None] * n_threads
		energy = [0.0] * n_threads
		self.timer.start("th_main")


		#print(gray[:,0:2])

		for i in range(n_threads):
			threads[i] = Thread(target=self.th_energy, args=(gray, self.prev_gray, self.width, self.th_length, energy, i))
			threads[i].start()

		h, s, v = colorsys.rgb_to_hsv(
			frame[:,:,2].mean()/255.0,
			frame[:,:,1].mean()/255.0,
			frame[:,:,0].mean()/255.0
			)
		self.next_frame, self.next_gray = self.capture_frame()

		self.timer.time("th_main")

		for i in range(n_threads):
			threads[i].join()
		
		self.prev_frame = frame
		self.prev_gray = gray
		return np.mean(energy), h, s, v
	

	def th_energy(self, gray, prev_gray, width, length, energy, i):
		"""
		Calculate the energy from the previous frame and the current frame.

		Args:
			frame: The current frame.
			prev_frame: The previous frame.
		"""
		th_name = "th"+str(i)
		self.timer.start(th_name)
		start = length * i
		end = start+length if i != self.n_threads-1 else width-1
		#print(f"th:{i}\t{start}\t{end}")

		# Calculate optical flow using Lucas-Kanade method
		
		flow = cv2.calcOpticalFlowFarneback(prev_gray[:,start:end], gray[:,start:end], None, 0.5, 3, 15, 3, 5, 1.2, 0)
		# Calculate the energy as the average of the magnitude of the flow vectors
	#	if i == 0:
	#		print(gray[:,start:end])
	#		print(f"len_flow: {len(flow[0])}, len_gray: {len(gray)}")
		energy[i] = np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2))
		#print(f"th({i}):\t{temp_energy}")
		self.timer.time(th_name)
		#print(f"thread ({i}) took {t1-t0} ns")

	
	def extract_properties(self, frame) -> tuple:
		"""
		Extract the properties from the current frame.

		Args:
			prev_frame: The previous frame.
			frame: The current frame.
		"""
		b = frame[:,:,0].mean()
		g = frame[:,:,1].mean()
		r = frame[:,:,2].mean()
		hsv = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
		return hsv




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
		#video_extractor = ExtractVideoProperties()
		#video_extractor.start_extracting(path, 320, 4)
		video_extractor = ExctractVideoProperties(path, 180)
		
		frames = []
		lenergy = []
		lhue = []
		lsaturation = []
		lbrightness = []

		ctimer = ComponentTimer()
		video_extractor.ctimer = ctimer
		#ctimer.start()

		i_frames = 0
		while video_extractor.status == RUNNING and i_frames < 100:
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

		#ctimer.time()

		print(ctimer.get_all_components())
		print(f"Took {(ctimer.get_sum())/1000000000.0} seconds.")
		#print(video_extractor.timer.get_all_components())

		#with open(path + ".txt", mode="wt") as f:
		#	f.write(str(frames))

		print("mean", np.mean(lenergy), np.mean(lhue), np.mean(lsaturation), np.mean(lbrightness))
		print("max", max(lenergy), max(lhue), max(lsaturation), max(lbrightness))

		


#mg.update_parameters(
#	energy/100000.0 if energy <= 100000.0 else 0,
#	hue/180,
#	saturation/255.0,
#	brightness/255.0)

