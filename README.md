# Princess iTunes 🎵

Modern desktop music player for Linux focused on **beautiful libraries, fluid navigation and a timeless listening experience**.

Princess iTunes reimagines the classic desktop music player by combining elegant interface design with modern Linux technologies and lightweight performance.

---

<p align="center">
  <img src="docs/demo.gif" alt="Princess iTunes Demo" width="100%">
</p>

---

# Features

## 🎶 Music Library

- Import local music folders
- Album browsing
- Artist browsing
- Playlist management
- Instant search
- Recently played
- Favorites

## 🎧 Playback

- Play / Pause / Next / Previous
- Shuffle
- Repeat
- Queue management
- Volume control
- Keyboard shortcuts

## 🎨 Interface

- Modern desktop interface
- Dark & Light themes
- Album artwork
- Smooth animations
- Responsive layouts

## 📚 Library Management

- Automatic library scanning
- Metadata support
- Album grouping
- Artist grouping
- Genre browsing

## ⚡ Performance

- Fast startup
- Optimized indexing
- Low memory usage
- Large music collections

---

# Tech Stack

- Python
- PySide6
- Qt6

---

# Application Architecture

```
Music Library
      │
      ▼
Metadata Scanner
      │
      ▼
Database
      │
      ▼
Library Browser
      │
      ▼
Playback Engine
      │
      ▼
Audio Output
```

---

# Roadmap

## Playback

- [ ] Gapless playback
- [ ] Crossfade
- [ ] Equalizer

## Library

- [ ] Smart playlists
- [ ] Advanced search
- [ ] Better metadata editing

## Integration

- [ ] MPRIS support
- [ ] Last.fm integration
- [ ] Internet radio
- [ ] Podcasts

## Interface

- [ ] Mini player
- [ ] Lyrics support
- [ ] Visualizer

---

# Installation

```bash
git clone https://github.com/princessnvidia/princess-itunes.git

cd princess-itunes

pip install -r requirements.txt

python princess_itunes.py
```

---

# Philosophy

Princess iTunes is built around the idea that listening to music on the desktop should feel enjoyable.

Instead of overwhelming users with countless options, the application focuses on smooth navigation, elegant library management and an interface designed to stay out of the way while your music remains the center of attention.

The long-term vision is to create a modern Linux music player inspired by the simplicity and polish of classic desktop applications while remaining fully open source.

---

# Inspiration

- iTunes
- Rhythmbox
- Elisa
- foobar2000
- Strawberry
- Dopamine

---

# Status

🚧 Active Development

---

# License

MIT License
