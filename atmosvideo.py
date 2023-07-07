from threading import Thread
from video_properties_2 import VideoPropertiesExtractor, ComponentTimer
from MusicGeneration import MusicGenerator
import sched
import numpy as np
import time

from pyaudio import PyAudio
from pydub import AudioSegment





class RoundBuffer():
	def __init__(self, size:int) -> None:
		self.values = [None] * size
		self.size = size
		self.id = 0
		self.full = False
	
	def write(self, value):
		self.values[self.id] = value

		self.id += 1
		if self.id >= self.size:
			self.id = 0
			self.full = True
	

class Property():
	def __init__(self):
		self.buffer = RoundBuffer(10)
		self.last_value = -10


class Atmosvideo():
	DISCONNECTED = 0
	RUNNING = 1
	FINISHED = 2
	ERROR = 3
	CANCELED = 4

	def __init__(self, sample_rate=44100, live=True):
		"""
		Creates an atmosvideo object and initializes its components.
		"""
		self.music = MusicGenerator(sample_rate, live)
		self.video = VideoPropertiesExtractor(180)
		self.timer = ComponentTimer()
		self.status = Atmosvideo.DISCONNECTED
		self.properties = (Property(), Property(), Property(), Property())
	
	def load(self, video_path:str):
		"""
		Loads atmosvideo with the video at the path given, and initializes its functionality.

		Args:
			video_path (str): The path to the video stream.
		"""
		self.i_frame = 0
		self.video.load(video_path)
		self.frame_time = 1/self.video.fps
		self.timer.start("atmosvideo")
		self.status = Atmosvideo.RUNNING
		self.force_update = True
		self.force_last_sample = 0
		self.samples_done = 0
	
	def start(self):
		nsamples_frame = round(self.music.samplerate/self.video.fps)
		print("samples per frame", nsamples_frame)
		samples = bytearray()
		while(self.status == Atmosvideo.RUNNING):
			self.frame()
			self.update_parameters(self.video.values)
			samples.extend(self.music.get_samples(nsamples_frame))
			self.samples_done += nsamples_frame
		
		print("samples done: " + str(self.samples_done))
		return bytes(samples)

	def frame(self):
		self.i_frame += 1
		running = self.video.step()
		e, h, s, v = self.video.values
		#print("Frame {:5d}: Energy: {:.3f}, Hue: {:.3f}, Saturation: {:.3f}, Value: {:.3f}".format(self.i_frame, e, h, s, v))
		if not running:
			self.timer.time("atmosvideo")
			print(f"Took {self.timer.get('atmosvideo')/1_000_000_000.0} seconds")
			self.status = Atmosvideo.FINISHED
	


	def update_parameters(self, parameters):
		for i in range(4):
			self.properties[i].buffer.write(parameters[i])

		if not self.properties[0].buffer.full:
			return
		
		if self.force_update or self.samples_done - self.force_last_sample > 4 * self.music.samplerate:
			self.force_update = False
			self.maybe_set_parameters(0.05)
		else:
			self.maybe_set_parameters(0.10)


	def maybe_set_parameters(self, distinction):
		new_parameters = [None] * 4
		avg_parameters = [None] * 4
		for i in range(4):
			avg_parameters[i] = np.mean(self.properties[i].buffer.values)
			if abs(self.properties[i].last_value - avg_parameters[i]) > distinction:
				new_parameters[i] = avg_parameters[i]
		self.set_parameters(new_parameters)



	def set_parameters(self, parameters):
		self.force_last_sample = self.samples_done
		for i in range(4):
			if parameters[i]:
				self.properties[i].last_value = parameters[i]

		#for i in range(4):
		#	if parameters[i] == None:
		#		parameters[i] = -float('inf')
		#print("Update Generators:\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}".format(parameters[0], parameters[1], parameters[2], parameters[3]))
		self.update_generators(parameters[0], parameters[1], parameters[2], parameters[3])



	# all video parameters normalized [0,1]
	def update_generators(self, energy_p, hue_p, saturation_p, value_p):
		#print(new_energy, hue, saturation, value)

		energy = energy_p if energy_p else self.properties[0].last_value
		hue = hue_p if hue_p else self.properties[1].last_value
		saturation = saturation_p if saturation_p else self.properties[2].last_value
		value = value_p if value_p else self.properties[3].last_value

		# tempo
		if energy_p:
			new_bpm = energy * 110 + 50
			old_bpm = self.music.bpm
			if abs(new_bpm - old_bpm) > old_bpm*0.2:
				#print("changing_bpm", new_bpm)
				self.music.setBPM(new_bpm)
				pass
			
			#self.music.melody.base_subdivision = energy
		
		# transposition
		if value_p:
			self.music.melody.transposition = value*3 - 1
			self.music.chords.transposition = 2*value-1 * (-1 if value<0.5 else 1)

		# melody parameters
		if saturation_p or energy_p or value_p:
			self.music.melody.rest_rate = 0.2
			#self.music.melody.subdivision_rate = saturation*0.5 if energy+value > 0.6 else 0
			#self.music.melody.subdivision_rate = saturation*0.5 if energy+value > 0.6 else 0

		# scale
		if hue_p:
			if hue < 0.5/6 or hue > 5.5/6:
				scale_name = "japanese"
			elif hue < 1.5/6:
				scale_name = "maj_pentatonic"
			elif hue < 2.5/6:
				scale_name = "maj"
			elif hue < 3.5/6:
				scale_name = "min_pentatonic"
			elif hue < 4.5/6:
				scale_name = "min"
			else:
				scale_name = "hmin"
			self.music.melody.scale = MusicGenerator.scales[scale_name]
			self.music.chords.scale = MusicGenerator.scales[scale_name]

		# chord type
		if saturation_p or energy_p:
			chord_value = 0.5*(saturation) + 0.5*(1-energy)
			if chord_value < 1/3:
				self.music.chords.chord_type = MusicGenerator.chord_types["power"]
			if chord_value < 2/3:
				self.music.chords.chord_type = MusicGenerator.chord_types["triad"]
			else:
				self.music.chords.chord_type = MusicGenerator.chord_types["seven"]
		
		# arpegios
		# modified by instrument

		# chord speed
		self.music.chords.beats_per_chord = 4.0

		# instrument selection
		# 
		# the volume is adjusted based on the instrument to keep the volume leveled
		if value_p or energy_p:
			#print("actual energy", energy)
			if value < 1/3:
				if energy < 1/6:
					self.music.synth.changeInstrument(self.music.channel["chords"],17, 89) # pad
					self.music.synth.changeInstrument(self.music.channel["melody"], 0,104) # sitar
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.7
					self.music.melody.volume = 0.5
				elif energy < 1/2:
					self.music.synth.changeInstrument(self.music.channel["chords"], 2, 92) # square
					self.music.synth.changeInstrument(self.music.channel["melody"], 2, 92) # square
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.7
				else:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0, 29) # electric guitar
					self.music.synth.changeInstrument(self.music.channel["melody"], 0, 34) # bass
					self.music.chords.arpeggio_freq = 4
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.7
			elif value < 2/3:
				if energy < 1/6:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0, 0) # piano
					self.music.synth.changeInstrument(self.music.channel["melody"], 0, 0) # piano
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.6
				elif energy < 1/2:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0, 0) # piano
					self.music.synth.changeInstrument(self.music.channel["melody"], 0, 71) # clarinet
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.6
				else:
					pass
			else:
				if energy < 1/6:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0, 4) # ep
					self.music.synth.changeInstrument(self.music.channel["melody"], 0, 4) # ep
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.6
				elif energy < 1/2:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0,107) # koto
					self.music.synth.changeInstrument(self.music.channel["melody"], 1,104) # tampura
					self.music.chords.arpeggio_freq = 2
					self.music.chords.volume = 0.5
					self.music.melody.volume = 0.5
				else:
					self.music.synth.changeInstrument(self.music.channel["chords"], 0, 61) # brass
					self.music.synth.changeInstrument(self.music.channel["melody"], 0, 60) # f.horn
					self.music.chords.arpeggio_freq = 0
					self.music.chords.volume = 0.45
					self.music.melody.volume = 0.55
	



if __name__ == "__main__":

	video_name = "v7" # name of the video
	sample_rate = 44100  # Sample rate in Hz	
	
	def play_audio(samples, sample_rate):
		p = PyAudio()

		stream = p.open(format=p.get_format_from_width(2),
						channels=2,
						rate=sample_rate,
						output=True)

		stream.write(samples)

		stream.stop_stream()
		stream.close()

		p.terminate()
	
	def write_mp3(samples, sample_rate, output_file):
		audio = AudioSegment(
			samples,
			frame_rate=sample_rate,
			sample_width=2,
			channels=2
		)
		audio.export(output_file, format='mp3')

	
	video_path = f'example_videos/{video_name}.mp4'

	atmos = Atmosvideo(sample_rate=sample_rate, live=False)
	atmos.load(video_path)
	samples = atmos.start()

	
	# Play the audio sample
	#play_audio(samples, sample_rate)

	output_file = f'sound_output/{video_name}.mp3'

	# Write the audio sample to an MP3 file
	write_mp3(samples, sample_rate, output_file)


	