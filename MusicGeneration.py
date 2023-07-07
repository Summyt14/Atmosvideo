import random
import time
import fluidsynth
import math
from sched import scheduler
import ast
from pydub import AudioSegment

from threading import Thread

import numpy
from pyaudio import PyAudio



class Synth():
	def __init__(self, samplerate=44100) -> None:
		fs = fluidsynth.Synth(gain=2.0, samplerate=samplerate)
		# select instruments
		self.sfid = fs.sfload("ColomboGMGS2.sf2")

		self.fs = fs

		# 2, 92 - good squarewave
		# 0, 107 - koto
		# 0, 40 - violin
		self.changeInstrument(0, 17, 89)
		self.changeInstrument(1, 0,104)
	
	def start(self):
		self.fs.start(driver="pulseaudio")

	
	def changeInstrument(self, channel:int, bank:int, instrument:int):
		set_sfid, set_bank, set_inst = self.fs.program_info(channel)
		#if set_bank != bank and set_inst != instrument:
		self.fs.program_select(channel, self.sfid, bank, instrument)





class MusicGenerator():

	scheduler = scheduler()

	# scales are defined in semitones
	scales = {
		"maj": [0,2,4,5,7,9,11],
		"min": [0,2,3,5,7,8,10],
		"hmin": [0,2,3,5,7,8,11],
		"maj_pentatonic": [0,2,4,4,7,7,9],
		"min_pentatonic": [0,3,3,5,7,7,10],
		"japanese": [0,2,3,3,7,8,8],
	}

	# chords are defined in notes of a scale
	chord_types = {
		"seven": [1,3,5,7],
		"triad": [1,3,5,8],
		"power": [1,5,8,12]
	}

	def __init__(self, samplerate=44100, live=True) -> None:
		scale = "maj"
		self.samplerate = samplerate
		self.synth = Synth(samplerate)
		if live:
			self.synth.start()
		self.melody = MelodyGenerator(self.scales[scale])
		self.chords = ChordGenerator(self.scales[scale])
		self.channel = {"melody": 1, "chords": 0}
		self.base_midi_note = 40
		self.bpm = 120
		self.do_restart = False
		self.do_stop = False
		self.energy_avg = 0
		self.tasks = []


	def update_melody(self):
		"""
		Called by the scheduler to change the melody note. The next update_melody() call is scheduled.
		"""
		self.update_handler(self.melody.next)

	def update_chords(self):
		"""
		Called by the scheduler to change the chord notes. The next update_chords() call is scheduled.
		"""
		self.update_handler(self.chords.next)
	
	def update_handler(self, next_action):
		if self.do_restart:
			self.melody.restart()
			self.chords.restart()
			self.do_restart = False
		next_action(self)

	
	def beats2time(self, beats:float):
		return beats * 60 / self.bpm

	def setBPM(self, bpm):
		self.do_restart = True
		self.bpm = bpm
	
	def setScale(self, scale:str):
		self.melody.scale = self.scales[scale]
		self.chords.scale = self.scales[scale]
	

	def note_from_scale(self, scale:list, note:int) -> int:
		octave = note // len(scale)
		note = note % len(scale)
		return self.base_midi_note + scale[note] + 12*octave



	def get_samples(self, nsamples:int):
		samples_done = 0
		samples = []

		run = True
		while(run):
			if self.melody.next_change_samples == 0:
				self.update_melody()
			if self.chords.next_change_samples == 0:
				self.update_chords()
			
			next_change = min(self.melody.next_change_samples, self.chords.next_change_samples)

			if next_change + samples_done > nsamples:
				batchsize = nsamples-samples_done
				run = False
			else:
				batchsize = next_change
			
			self.melody.next_change_samples -= batchsize
			self.chords.next_change_samples -= batchsize
			samples_done += batchsize
			new_samples = mg.synth.fs.get_samples(batchsize)
			samples = numpy.append(samples, new_samples)
		
		return fluidsynth.raw_audio_string(samples)




		


class MelodyGenerator():
	def __init__(self, scale) -> None:
		self.rnd:random.Random = random.Random()
		self.scale = scale
		self.subdivision_rate = 0.0
		self.rest_rate = 0.2
		self.transposition = 0
		self.volume = 0.5
		self.next_change_samples = 0
		self.note_midi = 0
	
	def next(self, mg:MusicGenerator):
		# disable preveously playing note
		mg.synth.fs.noteoff(mg.channel["melody"], self.note_midi)

		#calculate speed
		musical_duration = 1.0
		if self.rnd.random() < self.subdivision_rate:
			musical_duration /= 2
		duration = mg.beats2time(musical_duration)
		self.next_change_samples = int(duration * mg.samplerate)
		
		#decide if note is played or rest
		r = self.rnd.random()
		#rest 1/5 times
		if r > self.rest_rate:
			#calculate pitch
			r = self.rnd.random()
			scale_len = len(self.scale)
			note = math.floor((r + self.transposition) * scale_len)
			#note_octave = note // scale_len
			#note_index = note % scale_len
			#note_midi = mg.base_midi_note + self.scale[note_index] + 12*note_octave
			self.note_midi = mg.note_from_scale(self.scale, note)
			velocity = math.floor(self.volume * 127)

			mg.synth.fs.noteon(mg.channel["melody"], self.note_midi, velocity)
	
	def restart(self):
		self.next_change_samples = 0
	


class ChordGenerator():
	def __init__(self, scale) -> None:
		self.rnd:random.Random = random.Random()
		self.transposition = 0
		self.scale = scale
		self.chord_type = MusicGenerator.chord_types["triad"]
		#self.melody = melody
		self.arpeggio_freq = 0
		self.beats_per_chord = 4.0
		self.volume = 0.5
		self.notes_playing = []
		self.notes_to_arpeggiate = []
		self.current_arpeggio_note = 0
		self.arpeggio_note_duration = 0
		self.next_change_samples = 0

		
#	def mapSpeed(self, r):
#		return 4
	
	def next(self, mg:MusicGenerator):
		# disable preveously playing notes
		for note in self.notes_playing:
			mg.synth.fs.noteoff(mg.channel["chords"], note)
		self.notes_playing.clear()


		#calculate pitches
		scale_len = len(self.scale)
		mode = math.floor(self.rnd.random() * scale_len)
		#self.melody.mode = mode

		velocity = math.floor(self.volume * 127)
		duration = mg.beats2time(self.beats_per_chord)
		base_note = mg.base_midi_note + round(self.transposition * 12)
		if self.arpeggio_freq and not self.notes_to_arpeggiate:
			self.arpeggio_note_duration = duration / (len(self.chord_type) * self.arpeggio_freq)
			self.current_arpeggio_note = 0
			for i in range (0, self.arpeggio_freq):
				for note in self.chord_type:
					midi_note = mg.note_from_scale(self.scale, note-1 + mode + round(self.transposition*scale_len))
					self.notes_to_arpeggiate.append(midi_note)

		if self.notes_to_arpeggiate:
			midi_note = self.notes_to_arpeggiate[self.current_arpeggio_note]
			mg.synth.fs.noteon(mg.channel["chords"], midi_note, velocity)
			self.next_change_samples = int(self.arpeggio_note_duration * mg.samplerate)
			self.current_arpeggio_note += 1
			if self.current_arpeggio_note >= len(self.notes_to_arpeggiate):
				self.notes_to_arpeggiate.clear()

		if not self.arpeggio_freq and not self.notes_to_arpeggiate:
			self.next_change_samples = int(duration * mg.samplerate)
			for note in self.chord_type:
				midi_note = mg.note_from_scale(self.scale, note-1 + mode)
				mg.synth.fs.noteon(mg.channel["chords"], midi_note, velocity)
				self.notes_playing.append(midi_note)
	
	def restart(self):
		self.notes_playing.clear()
		self.notes_to_arpeggiate.clear()
		self.current_arpeggio_note = 0
		self.arpeggio_note_duration = 0
		self.next_change_samples = 0
	
	def calculate_note_midi(self, r):
		scale_len = len(self.scale)
		note = math.floor((r + self.transposition) * scale_len)
		note_octave = note // scale_len
		note_index = note % scale_len
		note_midi = mg.base_midi_note + self.scale[note_index] + 12*note_octave
		return note_midi
	
	


	


if __name__ == "__main__":

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

	# Example usage
	sample_rate = 44100  # Sample rate in Hz
	duration = 5  # Duration of the audio in seconds

	mg = MusicGenerator(samplerate=44100, live=False)

	samples = mg.get_samples(sample_rate * duration)

	output_file = 'output.mp3'

	# Write the audio sample to an MP3 file
	write_mp3(samples, sample_rate, output_file)


	# Play the audio sample
	play_audio(samples, sample_rate)

