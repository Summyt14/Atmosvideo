import random
import time
import fluidsynth
import math
from sched import scheduler

from threading import Thread




class Synth():
	def __init__(self) -> None:
		fs = fluidsynth.Synth(gain=3.0)
		fs.start(driver="pulseaudio")
		# select instruments
		self.sfid = fs.sfload("ColomboGMGS2.sf2")

		self.fs = fs

		# 2, 92 - good squarewave
		# 0, 107 - koto
		# 0, 40 - violin
		self.changeInstrument(0, 17, 89)
		self.changeInstrument(1, 0,104)
	
	def changeInstrument(self, channel:int, bank:int, instrument:int):
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

	def __init__(self) -> None:
		scale = "maj"
		self.synth = Synth()
		self.melody = MelodyGenerator(self.scales[scale])
		self.chords = ChordGenerator(self.scales[scale])
		self.channel = {"melody": 1, "chords": 0}
		self.base_midi_note = 40
		self.bpm = 120
		self.restart = False


	def start(self):
		self.next_melody_ts = time.monotonic()
		self.next_chords_ts = time.monotonic()
		self.update_melody()
		self.update_chords()
		self.scheduler.run()


	def update_melody(self):
		if self.restart:
			self.drain()
			return
		ts = self.next_melody_ts
		delay = self.melody.next(self, ts)
		self.next_melody_ts = ts + delay
		self.scheduler.enterabs(self.next_melody_ts, 1, self.update_melody)

	
	def update_chords(self):
		if self.restart:
			self.drain()
			return
		ts = self.next_chords_ts
		delay = self.chords.next(self, ts)
		self.next_chords_ts = ts + delay
		self.scheduler.enterabs(self.next_chords_ts, 1, self.update_chords)

	
	def beats2time(self, beats:float):
		return beats * 60 / self.bpm

	def setBPM(self, bpm):
		self.restart = True
		self.bpm = bpm
	
	def setScale(self, scale:str):
		self.melody.scale = self.scales[scale]
		self.chords.scale = self.scales[scale]
	
	def drain(self):
		if self.scheduler.empty():
			self.restart = False
			self.start()
		return

	def note_from_scale(self, scale:list, note:int) -> int:
		octave = note // len(scale)
		note  = note % len(scale)
		return self.base_midi_note + scale[note] + 12*octave
	
	
	# all video parameters normalized [0,1]
	def update_parameters(self, energy, hue, saturation, value, change_instrument):
		# tempo
		self.setBPM(energy * 120 + 30)
		
		# transposition
		self.melody.transposition = value*3 - 1
		self.chords.transposition = 2*value-1 * (-1 if value<0.5 else 1)

		# melody parameters
		self.melody.rest_rate = 0.2
		self.melody.subdivision_rate = saturation*0.5 if energy+value > 0.6 else 0

		# scale
		if hue < 0.5/6 or hue > 5.5/6:
			scale = "japanese"
		elif hue < 1.5/6:
			scale = "maj_pentatonic"
		elif hue < 2.5/6:
			scale = "maj"
		elif hue < 3.5/6:
			scale = "min_pentatonic"
		elif hue < 4.5/6:
			scale = "min"
		else:
			scale = "hmin"
		self.melody.scale = mg.scales[scale]
		self.chords.scale = mg.scales[scale]

		# chord type
		chord_value = 0.5*(saturation) + 0.5*(1-energy)
		if chord_value < 1/3:
			self.chords.chord_type = mg.chord_types["power"]
		if chord_value < 2/3:
			self.chords.chord_type = mg.chord_types["triad"]
		else:
			self.chords.chord_type = mg.chord_types["seven"]
		
		# arpegios
		# modified by instrument

		# chord speed
		self.chords.beats_per_chord = 4.0

		# instrument selection
		if change_instrument:
			if value < 1/3:
				if energy < 1/3:
					self.synth.changeInstrument(self.channel["chords"],17, 89) # pad
					self.synth.changeInstrument(self.channel["melody"], 0,104) # sitar
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.5
					self.melody.volume = 0.5
				elif energy < 2/3:
					self.synth.changeInstrument(self.channel["chords"], 2, 92) # square
					self.synth.changeInstrument(self.channel["melody"], 2, 92) # square
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.5
					self.melody.volume = 0.7
				else:
					self.synth.changeInstrument(self.channel["chords"], 0, 29) # electric guitar
					self.synth.changeInstrument(self.channel["melody"], 0, 34) # bass
					self.chords.arpeggio_freq = 4
					self.chords.volume = 0.5
					self.melody.volume = 0.7
			elif value < 2/3:
				if energy < 1/3:
					self.synth.changeInstrument(self.channel["chords"], 0, 0) # piano
					self.synth.changeInstrument(self.channel["melody"], 0, 0) # piano
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.5
					self.melody.volume = 0.6
				elif energy < 2/3:
					self.synth.changeInstrument(self.channel["chords"], 0, 0) # piano
					self.synth.changeInstrument(self.channel["melody"], 0, 71) # clarinet
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.5
					self.melody.volume = 0.6
				else:
					pass
			else:
				if energy < 1/3:
					self.synth.changeInstrument(self.channel["chords"], 0, 4) # ep
					self.synth.changeInstrument(self.channel["melody"], 0, 4) # ep
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.5
					self.melody.volume = 0.6
				elif energy < 2/3:
					self.synth.changeInstrument(self.channel["chords"], 0,107) # koto
					self.synth.changeInstrument(self.channel["melody"], 1,104) # tampura
					self.chords.arpeggio_freq = 2
					self.chords.volume = 0.5
					self.melody.volume = 0.5
				else:
					self.synth.changeInstrument(self.channel["chords"], 0, 61) # brass
					self.synth.changeInstrument(self.channel["melody"], 0, 60) # f.horn
					self.chords.arpeggio_freq = 0
					self.chords.volume = 0.45
					self.melody.volume = 0.55






class MelodyGenerator():
	def __init__(self, scale) -> None:
		self.rnd:random.Random = random.Random()
		self.scale = scale
		self.subdivision_rate = 0.0
		self.rest_rate = 0.2
		self.transposition = 0
		self.volume = 0.5

	
	def next(self, mg:MusicGenerator, ts):		
		#calculate speed
		musical_duration = 1.0
		if self.rnd.random() < self.subdivision_rate:
			musical_duration /= 2
		duration = mg.beats2time(musical_duration)
		
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
			note_midi = mg.note_from_scale(self.scale, note)
			velocity = math.floor(self.volume * 127)

			mg.scheduler.enterabs(ts, 1, mg.synth.fs.noteon, (mg.channel["melody"], note_midi, velocity))
			mg.scheduler.enterabs(ts + duration, 1, mg.synth.fs.noteoff, (mg.channel["melody"], note_midi))
		
		return duration
	


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
		
	def mapSpeed(self, r):
		return 4
	
	def next(self, mg:MusicGenerator, ts):
		#calculate pitches
		scale_len = len(self.scale)
		mode = math.floor(self.rnd.random() * scale_len)
		#self.melody.mode = mode

		velocity = math.floor(self.volume * 127)
		duration = mg.beats2time(self.beats_per_chord)
		base_note = mg.base_midi_note + round(self.transposition * 12)
		if self.arpeggio_freq:
			note_duration = duration / (len(self.chord_type) * self.arpeggio_freq)

			note_space = mg.beats2time(self.beats_per_chord / (len(self.chord_type) * self.arpeggio_freq))
			note_start = ts
			for i in range (0, self.arpeggio_freq):
				for note in self.chord_type:
					midi_note = mg.note_from_scale(self.scale, note-1 + mode + round(self.transposition*scale_len))
					#midi_note = self.calculate_note_midi()
					mg.scheduler.enterabs(note_start, 1, mg.synth.fs.noteon, (mg.channel["chords"], midi_note, velocity))
					mg.scheduler.enterabs(note_start + note_duration, 1, mg.synth.fs.noteoff, (mg.channel["chords"], midi_note))
					note_start += note_space
		else:
			for note in self.chord_type:
				midi_note = mg.note_from_scale(self.scale, note-1 + mode)
				mg.scheduler.enterabs(ts, 1, mg.synth.fs.noteon, (mg.channel["chords"], midi_note, velocity))
				mg.scheduler.enterabs(ts + duration, 1, mg.synth.fs.noteoff, (mg.channel["chords"], midi_note))
		
		return duration
	
	def calculate_note_midi(self, r):
		scale_len = len(self.scale)
		note = math.floor((r + self.transposition) * scale_len)
		note_octave = note // scale_len
		note_index = note % scale_len
		note_midi = mg.base_midi_note + self.scale[note_index] + 12*note_octave
		return note_midi





if __name__ == "__main__":

	mg = MusicGenerator()



	mg.update_parameters(0.9, 0.8, 0.9, 0.2, True)

	Thread(target=mg.start).start()
