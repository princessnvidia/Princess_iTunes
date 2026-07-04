#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Princess iTunes V59 — KDE dock/app-id fix
Mini iTunes en Python / PyQt6.

V55 update :
- Restaure la transparence de la liste des titres avec la table virtualisée QTableView.
- Le mode grosses playlists sans lag est conservé.

V59 update :
- Fix KDE/Plasma renforcé : AppID Wayland + DesktopFileName + WM_CLASS.
- DesktopEntry MPRIS aligné sur org.princess.Princess_iTunes.
- Transparence des titres conservée.

V54 update :
- Mode grosses playlists : table virtualisée avec QTableView + QAbstractTableModel.
- Suppression du resizeRowsToContents() qui faisait laguer les très grandes playlists.
- Rescan automatique périodique désactivé pour éviter les freezes toutes les 3 secondes.
- Scan de durées automatique désactivé pour éviter ffprobe en boucle sur des milliers de sons.
- Le rescan se fait encore au lancement et quand un dossier est ajouté.

V49 update :
- Test visuel full transparence : fonds beaucoup plus transparents sur toute l’app.
- Les panneaux, la sidebar, la table, les boutons et la barre du bas deviennent plus glass/transparent.
- Le texte reste lisible et les fonctions existantes sont conservées.

V46 update :
- Le bouton boucle alterne maintenant entre boucle playlist, boucle morceau et aucune boucle.
- Icône ↻ pour playlist, ↻1 pour morceau, ⤬ pour aucune boucle.

V42 update :
- Suppression des icônes devant les titres des morceaux.

V41 update :
- Affichage de la durée réelle des morceaux dans la colonne Durée.
- Durées calculées avec ffprobe si disponible, sans aifc ni scan Qt dangereux.
- Les durées sont sauvegardées dans library.json.
- La barre Espace contrôle à nouveau play/pause même si la table a le focus.

V33 update :
- Les dossiers ajoutés sont enregistrés comme sources et rescannés automatiquement.
- Les ajouts/modifications/suppressions dans ces dossiers sont synchronisés au lancement et périodiquement.
- Le clic simple lance toujours la lecture.
- La sélection ne change plus la couleur : le morceau en cours est simplement en gras.

V30 update :
- Suppression de l’entrée “Bibliothèque” dans la colonne de gauche.
- La colonne de gauche n’affiche plus que les playlists/dossiers ajoutés.
- Quand aucune playlist n’est sélectionnée, la liste reste vide jusqu’à sélection/ajout.

V29 update :
- La colonne de gauche n’affiche plus le nombre de titres par playlist.
- La colonne de gauche est redimensionnable à la souris via une séparation centrale.

V28 update :
- Les titres sont reconstruits depuis les noms de fichiers au chargement.
- Les anciens titres sauvegardés sans "-" récupèrent automatiquement leurs tirets.
- Le caractère "-" est conservé dans tous les affichages de titre.

V27 update :
- Le caractère "-" est conservé dans les titres affichés.
- L'icône pause utilise "❚❚" pour un rendu plus propre.
- Conservation des touches média KDE/MPRIS et du focus de recherche corrigé.

V26 update :
- Retour au symbole pause fin "Ⅱ", même gabarit visuel que les autres boutons.
- Alignement vertical du bouton pause stabilisé après clic sur Play.
- Conservation des touches média KDE/MPRIS et du focus de recherche corrigé.

V25 update :
- Le champ Rechercher ne prend plus le focus au lancement.
- Le champ Rechercher ne prend le focus qu’après clic.
- Icônes transport redescendues de 1 px.
- Icône pause remplacée par une version plus propre et mieux alignée.

V16 :
- Plus aucun scan automatique de ~/Musique.
- Bibliothèque vide au premier démarrage.
- Ajout manuel de fichiers audio.
- Ajout manuel d'un dossier audio.
- Les ajouts sont triés alphabétiquement.
- Les playlists/dossiers ajoutés sont sauvegardés automatiquement.
- Boutons façon iTunes : shuffle, précédent, lecture/pause, suivant, boucle playlist.
- Ignore les fichiers/dossiers commençant par un point.
- Interface sombre/translucide #33333B inspirée iTunes / PrincessFinder.
"""

import sys
import json
import os
import random
import shutil
import subprocess
import ctypes
import ctypes.util
from ctypes import Structure, c_char_p, c_void_p, POINTER
from pathlib import Path
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QUrl, QSize, QObject, pyqtSignal, QEvent, QTimer, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor, QAction, QBrush
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QHeaderView,
    QSlider,
    QFrame,
    QSizePolicy,
    QSplitter,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# Support optionnel des touches média globales via MPRIS/DBus.
# Sur KDE, les touches clavier Play/Pause, Previous et Next passent souvent
# par MPRIS plutôt que par les événements clavier de la fenêtre.
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    HAS_MPRIS = True
except Exception:
    HAS_MPRIS = False



APP_TITLE = "Princess iTunes"
APP_ID = "org.princess.Princess_iTunes"
UI_FONT = "DejaVu Sans"
BG = QColor(51, 51, 59, 77)
PANEL = "rgba(51, 51, 59, 77)"
PANEL_DARK = "rgba(32, 32, 39, 77)"
PANEL_LIGHT = "rgba(255, 255, 255, 18)"
PINK = "#ff8bd8"
TEXT = "rgba(255,255,255,230)"
DIM = "rgba(220,220,230,150)"


# KDE/Plasma Wayland utilise cet AppID pour grouper la fenêtre avec le lanceur .desktop.
# Il doit correspondre au nom du fichier : ~/.local/share/applications/org.princess.Princess_iTunes.desktop
os.environ.setdefault("QT_WAYLAND_APP_ID", APP_ID)
os.environ.setdefault("QT_XCB_WINDOW_CLASS", APP_ID)

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".aiff", ".aif"
}

APP_CONFIG_DIR = Path.home() / ".local/share/Princess_iTunes"
LIBRARY_FILE = APP_CONFIG_DIR / "library.json"
SOURCES_FILE = APP_CONFIG_DIR / "sources.json"


@dataclass
class Track:
    path: Path
    title: str
    artist: str = ""
    album: str = ""
    playlist: str = "Bibliothèque"
    source_root: str = ""
    duration_ms: int = 0


def is_hidden_path(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts if part not in ("/", ""))


def clean_title(path: Path) -> str:
    stem = path.stem.replace("_", " ").strip()
    return " ".join(stem.split()) or path.name


def themed_icon(*names: str) -> QIcon:
    for name in names:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon()




class XClassHint(Structure):
    _fields_ = [
        ("res_name", c_char_p),
        ("res_class", c_char_p),
    ]


def set_x11_wm_class(widget: QWidget):
    """
    Force WM_CLASS on X11 so KDE/Plasma groups the running window with
    ~/.local/share/applications/org.princess.Princess_iTunes.desktop.
    Safe no-op on Wayland or when libX11 is unavailable.
    """
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return

    if not os.environ.get("DISPLAY"):
        return

    lib_name = ctypes.util.find_library("X11")
    if not lib_name:
        return

    try:
        x11 = ctypes.cdll.LoadLibrary(lib_name)
        x11.XOpenDisplay.argtypes = [c_char_p]
        x11.XOpenDisplay.restype = c_void_p
        x11.XSetClassHint.argtypes = [c_void_p, ctypes.c_ulong, POINTER(XClassHint)]
        x11.XSetClassHint.restype = ctypes.c_int
        x11.XFlush.argtypes = [c_void_p]
        x11.XFlush.restype = ctypes.c_int
        x11.XCloseDisplay.argtypes = [c_void_p]
        x11.XCloseDisplay.restype = ctypes.c_int

        display = x11.XOpenDisplay(None)
        if not display:
            return

        hint = XClassHint()
        hint.res_name = APP_ID.encode("utf-8")
        hint.res_class = APP_ID.encode("utf-8")
        x11.XSetClassHint(display, int(widget.winId()), ctypes.byref(hint))
        x11.XFlush(display)
        x11.XCloseDisplay(display)
    except Exception:
        pass


class MediaBridge(QObject):
    play_pause_requested = pyqtSignal()
    next_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()


if HAS_MPRIS:
    class MPRISService(dbus.service.Object):
        ROOT_IFACE = "org.mpris.MediaPlayer2"
        PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
        PROPS_IFACE = "org.freedesktop.DBus.Properties"

        def __init__(self, app_window, bridge):
            self.app_window = app_window
            self.bridge = bridge
            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SessionBus()
            self.bus_name = dbus.service.BusName(
                "org.mpris.MediaPlayer2.Princess_iTunes",
                bus=self.bus,
                allow_replacement=True,
                replace_existing=True,
                do_not_queue=True,
            )
            super().__init__(self.bus_name, "/org/mpris/MediaPlayer2")

        def player_props(self):
            status = "Playing" if self.app_window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState else "Paused"
            return {
                "PlaybackStatus": dbus.String(status),
                "LoopStatus": dbus.String(self.app_window.mpris_loop_status()),
                "Rate": dbus.Double(1.0),
                "Shuffle": dbus.Boolean(self.app_window.shuffle_enabled),
                "Metadata": self.metadata(),
                "Volume": dbus.Double(float(self.app_window.audio.volume())),
                "Position": dbus.Int64(int(self.app_window.player.position()) * 1000),
                "MinimumRate": dbus.Double(1.0),
                "MaximumRate": dbus.Double(1.0),
                "CanGoNext": dbus.Boolean(True),
                "CanGoPrevious": dbus.Boolean(True),
                "CanPlay": dbus.Boolean(True),
                "CanPause": dbus.Boolean(True),
                "CanSeek": dbus.Boolean(True),
                "CanControl": dbus.Boolean(True),
            }

        def root_props(self):
            return {
                "CanQuit": dbus.Boolean(False),
                "Fullscreen": dbus.Boolean(False),
                "CanSetFullscreen": dbus.Boolean(False),
                "CanRaise": dbus.Boolean(True),
                "HasTrackList": dbus.Boolean(False),
                "Identity": dbus.String("Princess iTunes"),
                "DesktopEntry": dbus.String(APP_ID),
                "SupportedUriSchemes": dbus.Array(["file"], signature="s"),
                "SupportedMimeTypes": dbus.Array([
                    "audio/mpeg", "audio/flac", "audio/ogg", "audio/wav", "audio/aac", "audio/mp4"
                ], signature="s"),
            }

        def metadata(self):
            track = None
            if self.app_window.current_index is not None and 0 <= self.app_window.current_index < len(self.app_window.tracks):
                track = self.app_window.tracks[self.app_window.current_index]

            if track is None:
                return dbus.Dictionary({}, signature="sv")

            return dbus.Dictionary({
                "mpris:trackid": dbus.ObjectPath("/org/princess/Princess_iTunes/current"),
                "xesam:title": dbus.String(track.title),
                "xesam:artist": dbus.Array([dbus.String(track.artist or "")], signature="s"),
                "xesam:album": dbus.String(track.album or track.playlist or ""),
                "xesam:url": dbus.String(QUrl.fromLocalFile(str(track.path)).toString()),
            }, signature="sv")

        @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
        def Raise(self):
            QTimer.singleShot(0, self.app_window.raise_)

        @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
        def Quit(self):
            pass

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Next(self):
            self.bridge.next_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Previous(self):
            self.bridge.previous_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Pause(self):
            self.bridge.pause_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def PlayPause(self):
            self.bridge.play_pause_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Stop(self):
            self.bridge.stop_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Play(self):
            self.bridge.play_requested.emit()

        @dbus.service.method(PLAYER_IFACE, in_signature="x", out_signature="")
        def Seek(self, offset):
            QTimer.singleShot(0, lambda: self.app_window.player.setPosition(
                max(0, self.app_window.player.position() + int(offset / 1000))
            ))

        @dbus.service.method(PLAYER_IFACE, in_signature="ox", out_signature="")
        def SetPosition(self, trackid, position):
            QTimer.singleShot(0, lambda: self.app_window.player.setPosition(max(0, int(position / 1000))))

        @dbus.service.method(PLAYER_IFACE, in_signature="s", out_signature="")
        def OpenUri(self, uri):
            pass

        @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
        def Get(self, interface_name, property_name):
            props = self.GetAll(interface_name)
            if property_name in props:
                return props[property_name]
            raise dbus.exceptions.DBusException("org.freedesktop.DBus.Error.InvalidArgs", "Unknown property")

        @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface_name):
            if interface_name == self.ROOT_IFACE:
                return dbus.Dictionary(self.root_props(), signature="sv")
            if interface_name == self.PLAYER_IFACE:
                return dbus.Dictionary(self.player_props(), signature="sv")
            return dbus.Dictionary({}, signature="sv")

        @dbus.service.method(PROPS_IFACE, in_signature="ssv", out_signature="")
        def Set(self, interface_name, property_name, value):
            if interface_name != self.PLAYER_IFACE:
                return
            if property_name == "Shuffle":
                QTimer.singleShot(0, lambda: self.app_window.set_shuffle(bool(value)))
            elif property_name == "LoopStatus":
                loop_value = str(value)
                if loop_value == "Track":
                    QTimer.singleShot(0, lambda: self.app_window.set_repeat_mode("track"))
                elif loop_value == "None":
                    QTimer.singleShot(0, lambda: self.app_window.set_repeat_mode("off"))
                else:
                    QTimer.singleShot(0, lambda: self.app_window.set_repeat_mode("playlist"))
            elif property_name == "Volume":
                QTimer.singleShot(0, lambda: self.app_window.audio.setVolume(float(value)))

        @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
        def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
            pass

        def notify_player_changed(self):
            try:
                self.PropertiesChanged(
                    self.PLAYER_IFACE,
                    dbus.Dictionary(self.player_props(), signature="sv"),
                    dbus.Array([], signature="s"),
                )
            except Exception:
                pass
else:
    MPRISService = None



class TrackTableModel(QAbstractTableModel):
    HEADERS = ["Nom", "Artiste", "Album", "Playlist", "Durée"]

    def __init__(self, app_window):
        super().__init__(app_window)
        self.app_window = app_window

    def rowCount(self, parent=QModelIndex()):
        return len(self.app_window.filtered_indices)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (0 <= row < len(self.app_window.filtered_indices)):
            return None

        track_index = self.app_window.filtered_indices[row]
        if not (0 <= track_index < len(self.app_window.tracks)):
            return None

        track = self.app_window.tracks[track_index]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return track.title
            if col == 1:
                return track.artist
            if col == 2:
                return track.album
            if col == 3:
                return track.playlist
            if col == 4:
                return self.app_window.format_time(track.duration_ms) if track.duration_ms else "--:--"

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QBrush(QColor(255, 255, 255, 230))
            return QBrush(QColor(220, 220, 230, 170))

        if role == Qt.ItemDataRole.FontRole and track_index == self.app_window.current_index:
            font = QFont(UI_FONT, 10)
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.UserRole:
            return track_index

        return None

class GlassPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)


class PrincessITunes(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1120, 680)
        self.setMinimumSize(900, 560)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.tracks: list[Track] = []
        self.filtered_indices: list[int] = []
        self.current_index: int | None = None
        self.current_playlist = ""
        self.user_is_sliding = False
        self.shuffle_enabled = False
        self.repeat_mode = "off"
        self.repeat_enabled = False  # compatibilité interne/MPRIS : True si repeat_mode != "off"
        self.folder_sources: list[Path] = []
        self.rescan_timer = QTimer(self)
        self.rescan_timer.setInterval(60000)
        self.rescan_timer.timeout.connect(self.rescan_saved_folders)

        self.duration_scan_queue: list[int] = []
        self.duration_scan_running = False
        self.duration_timer = QTimer(self)
        self.duration_timer.setInterval(250)
        self.duration_timer.timeout.connect(self.scan_next_duration)

        self.media_bridge = MediaBridge(self)
        self.mpris_service = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.75)

        self.build_ui()
        self.connect_player()
        self.connect_media_keys()
        self.setup_mpris()
        self.load_sources()
        self.load_library()
        self.rescan_saved_folders(initial=True)
        self.refresh_all()
        self.update_repeat_button()
        self.update_shuffle_button()
        self.queue_missing_durations()
        # V54 : désactivé par défaut pour les grosses playlists.
        # Le rescan reste fait au lancement et lors de l'ajout d'un dossier.
        # self.rescan_timer.start()
        # self.duration_timer.start()
        QTimer.singleShot(0, lambda: self.setFocus(Qt.FocusReason.OtherFocusReason))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BG)

    def build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                color: {TEXT};
                font-family: '{UI_FONT}';
                font-size: 13px;
            }}
            #Root {{
                background: rgba(0,0,0,0);
            }}
            #TopBar {{
                background: rgba(35,35,42,77);
                border-bottom: 1px solid rgba(255,255,255,28);
            }}
            #Sidebar {{
                background: rgba(43,43,51,77);
                border-right: 1px solid rgba(255,255,255,28);
            }}
            QSplitter::handle {{
                background: rgba(255,255,255,28);
                width: 5px;
            }}
            QSplitter::handle:hover {{
                background: rgba(255,255,255,34);
            }}
            #PlayerBox {{
                background: rgba(25,25,31,86);
                border: 1px solid rgba(255,255,255,28);
                border-radius: 10px;
            }}
            QLabel#AppTitle {{
                font-size: 14px;
                font-weight: 700;
                color: rgba(255,255,255,230);
            }}
            QLabel#NowTitle {{
                font-size: 13px;
                font-weight: 700;
                color: rgba(255,255,255,235);
            }}
            QLabel#NowSubtitle {{
                font-size: 11px;
                color: {DIM};
            }}
            QPushButton {{
                background: rgba(255,255,255,38);
                color: rgba(255,255,255,225);
                border: 1px solid rgba(255,255,255,28);
                border-radius: 8px;
                padding: 7px 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,30);
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,38);
            }}
            QPushButton:focus {{
                outline: none;
                border: 1px solid rgba(255,255,255,28);
            }}
            QPushButton:checked {{
                background: rgba(255, 139, 216, 0);
                border: 1px solid rgba(255, 139, 216, 72);
                color: white;
            }}
            QPushButton#Transport {{
                min-width: 34px;
                max-width: 34px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                padding: 0px;
                font-size: 14px;
                outline: none;
            }}
            QPushButton#MainTransport {{
                min-width: 34px;
                max-width: 34px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                padding-left: 0px;
                padding-right: 0px;
                padding-top: 0px;
                padding-bottom: 3px;
                font-size: 14px;
                outline: none;
            }}
            QPushButton#Transport:focus,
            QPushButton#MainTransport:focus {{
                outline: none;
                border: 1px solid rgba(255,255,255,28);
            }}
            QPushButton#Transport:pressed,
            QPushButton#MainTransport:pressed {{
                outline: none;
            }}
            QPushButton#PrimaryButton {{
                background: rgba(255, 139, 216, 20);
                border: 1px solid rgba(255, 139, 216, 48);
            }}
            QLineEdit {{
                background: rgba(255,255,255,38);
                border: 1px solid rgba(255,255,255,28);
                border-radius: 9px;
                padding: 7px 11px;
                color: rgba(255,255,255,230);
                selection-background-color: rgba(255,139,216,38);
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                min-height: 30px;
                padding: 5px 10px;
                border-radius: 7px;
                color: rgba(255,255,255,205);
            }}
            QListWidget::item:selected {{
                background: rgba(255,255,255,30);
                color: white;
            }}
            QListWidget::item:hover {{
                background: rgba(255,255,255,38);
            }}
            QTableView {{
                background: rgba(51, 51, 59, 72);
                background-color: rgba(51, 51, 59, 72);
                border: none;
                gridline-color: rgba(255,255,255,28);
                selection-background-color: rgba(0,0,0,0);
                selection-color: rgba(255,255,255,230);
                alternate-background-color: rgba(255,255,255,0);
                outline: none;
            }}
            QTableView::viewport {{
                background: rgba(51, 51, 59, 72);
                background-color: rgba(51, 51, 59, 72);
            }}
            QTableView::item {{
                padding: 6px 8px;
                border: none;
                background: rgba(0,0,0,0);
            }}
            QTableView::item:selected {{
                background: rgba(0,0,0,0);
                color: rgba(255,255,255,230);
                border: none;
                outline: none;
            }}
            QTableWidget {{
                background: rgba(51, 51, 59, 72);
                border: none;
                gridline-color: rgba(255,255,255,28);
                selection-background-color: rgba(0,0,0,0);
                selection-color: rgba(255,255,255,230);
                alternate-background-color: rgba(255,255,255,0);
                outline: none;
            }}
            QHeaderView::section {{
                background: rgba(35,35,42,77);
                color: rgba(255,255,255,195);
                border: none;
                border-right: 1px solid rgba(255,255,255,22);
                border-bottom: 1px solid rgba(255,255,255,22);
                padding: 7px 8px;
                font-weight: 700;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: rgba(0,0,0,0);
                color: rgba(255,255,255,230);
                border: none;
                outline: none;
            }}
            QSlider::groove:horizontal {{
                height: 5px;
                background: rgba(255,255,255,30);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0px;
                border-radius: 7px;
                background: rgba(255,255,255,185);
            }}
        """)

        root = QVBoxLayout(self)
        root.setObjectName("Root")
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(10)

        # Contrôles façon iTunes : shuffle, précédent, lecture, suivant, boucle.
        self.shuffle_btn = QPushButton("⇄")
        self.prev_btn = QPushButton("◀◀")
        self.play_btn = QPushButton("▶")
        self.next_btn = QPushButton("▶▶")
        self.repeat_btn = QPushButton("↻")

        self.shuffle_btn.setToolTip("Lecture aléatoire")
        self.prev_btn.setToolTip("Morceau précédent")
        self.play_btn.setToolTip("Lecture / pause")
        self.next_btn.setToolTip("Morceau suivant")
        self.repeat_btn.setToolTip("Boucle playlist")

        self.shuffle_btn.setCheckable(True)
        self.repeat_btn.setCheckable(True)
        self.update_repeat_button()

        self.shuffle_btn.setObjectName("Transport")
        self.repeat_btn.setObjectName("Transport")
        for b in (self.prev_btn, self.play_btn, self.next_btn):
            b.setObjectName("MainTransport")

        for b in (self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn, self.repeat_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.now_box = QFrame()
        self.now_box.setObjectName("PlayerBox")
        now_layout = QVBoxLayout(self.now_box)
        now_layout.setContentsMargins(14, 7, 14, 7)
        now_layout.setSpacing(1)
        self.now_title = QLabel("Aucun morceau")
        self.now_title.setObjectName("NowTitle")
        self.now_subtitle = QLabel("Ajoute des fichiers ou un dossier pour commencer")
        self.now_subtitle.setObjectName("NowSubtitle")
        self.now_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.now_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        now_layout.addWidget(self.now_title)
        now_layout.addWidget(self.now_subtitle)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher")
        self.search.setFixedWidth(220)
        self.search.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        top_layout.addWidget(self.shuffle_btn)
        top_layout.addWidget(self.prev_btn)
        top_layout.addWidget(self.play_btn)
        top_layout.addWidget(self.next_btn)
        top_layout.addWidget(self.repeat_btn)
        top_layout.addWidget(self.now_box, 1)
        top_layout.addWidget(self.search)
        root.addWidget(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        root.addWidget(splitter, 1)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(150)
        sidebar.setMaximumWidth(420)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 14, 12, 14)
        side_layout.setSpacing(10)

        title = QLabel("Princess iTunes")
        title.setObjectName("AppTitle")
        side_layout.addWidget(title)

        self.sidebar = QListWidget()
        side_layout.addWidget(self.sidebar, 1)

        self.add_files_btn = QPushButton("+ Ajouter fichiers")
        self.add_files_btn.setObjectName("PrimaryButton")
        self.add_folder_btn = QPushButton("+ Ajouter dossier")
        self.clear_btn = QPushButton("Vider")
        side_layout.addWidget(self.add_files_btn)
        side_layout.addWidget(self.add_folder_btn)
        side_layout.addWidget(self.clear_btn)
        splitter.addWidget(sidebar)

        main_panel = QFrame()
        main_panel.setObjectName("MainPanel")
        main = QVBoxLayout(main_panel)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        splitter.addWidget(main_panel)
        splitter.setSizes([225, max(675, self.width() - 225)])

        self.table = QTableView()
        self.table.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table_model = TrackTableModel(self)
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        main.addWidget(self.table, 1)

        bottom = QFrame()
        bottom.setObjectName("TopBar")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(14, 8, 14, 8)
        bottom_layout.setSpacing(12)
        self.time_left = QLabel("00:00")
        self.time_right = QLabel("00:00")
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 0)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(75)
        self.volume.setFixedWidth(120)
        bottom_layout.addWidget(self.time_left)
        bottom_layout.addWidget(self.progress, 1)
        bottom_layout.addWidget(self.time_right)
        bottom_layout.addWidget(QLabel("Volume"))
        bottom_layout.addWidget(self.volume)
        main.addWidget(bottom)

        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.clear_btn.clicked.connect(self.clear_library)
        self.sidebar.currentRowChanged.connect(self.on_sidebar_changed)
        self.search.textChanged.connect(self.refresh_table)
        self.table.clicked.connect(self.play_clicked_row)
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.play_btn.clicked.connect(self.toggle_play)
        self.prev_btn.clicked.connect(self.previous_track)
        self.next_btn.clicked.connect(self.next_track)
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        self.volume.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.progress.sliderPressed.connect(self.on_slider_pressed)
        self.progress.sliderReleased.connect(self.on_slider_released)
        self.progress.sliderMoved.connect(self.on_slider_moved)


    def connect_media_keys(self):
        self.media_bridge.play_pause_requested.connect(self.toggle_play)
        self.media_bridge.next_requested.connect(self.next_track)
        self.media_bridge.previous_requested.connect(self.previous_track)
        self.media_bridge.play_requested.connect(self.play_from_media_key)
        self.media_bridge.pause_requested.connect(self.pause_from_media_key)
        self.media_bridge.stop_requested.connect(self.stop_from_media_key)
        QApplication.instance().installEventFilter(self)

    def setup_mpris(self):
        if not HAS_MPRIS or MPRISService is None:
            return

        try:
            self.mpris_service = MPRISService(self, self.media_bridge)
            self._mpris_loop = GLib.MainLoop()

            import threading
            self._mpris_thread = threading.Thread(
                target=self._mpris_loop.run,
                daemon=True,
            )
            self._mpris_thread.start()
        except Exception:
            self.mpris_service = None

    def notify_mpris(self):
        if self.mpris_service is not None:
            self.mpris_service.notify_player_changed()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            if key == Qt.Key.Key_Space and watched is not self.search:
                self.toggle_play()
                return True

            if key in (Qt.Key.Key_MediaPlay, Qt.Key.Key_MediaTogglePlayPause):
                self.toggle_play()
                return True

            if key == Qt.Key.Key_MediaPause:
                self.pause_from_media_key()
                return True

            if key == Qt.Key.Key_MediaNext:
                self.next_track()
                return True

            if key == Qt.Key.Key_MediaPrevious:
                self.previous_track()
                return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_Space:
            self.toggle_play()
            event.accept()
            return

        if key in (Qt.Key.Key_MediaPlay, Qt.Key.Key_MediaTogglePlayPause):
            self.toggle_play()
            event.accept()
            return

        if key == Qt.Key.Key_MediaPause:
            self.pause_from_media_key()
            event.accept()
            return

        if key == Qt.Key.Key_MediaNext:
            self.next_track()
            event.accept()
            return

        if key == Qt.Key.Key_MediaPrevious:
            self.previous_track()
            event.accept()
            return

        super().keyPressEvent(event)

    def play_from_media_key(self):
        if self.player.source().isEmpty():
            self.toggle_play()
        else:
            self.player.play()

    def pause_from_media_key(self):
        if not self.player.source().isEmpty():
            self.player.pause()

    def stop_from_media_key(self):
        self.player.stop()
        self.notify_mpris()

    def update_shuffle_button(self):
        if self.shuffle_enabled:
            self.shuffle_btn.setStyleSheet(
                "color: rgba(255,255,255,230); "
                "background: rgba(255,139,216,32); "
                "border: 1px solid rgba(255,139,216,72);"
            )
        else:
            self.shuffle_btn.setStyleSheet("")

    def set_shuffle(self, enabled: bool):
        self.shuffle_enabled = bool(enabled)
        self.shuffle_btn.setChecked(self.shuffle_enabled)
        self.update_shuffle_button()
        self.notify_mpris()


    def mpris_loop_status(self):
        if self.repeat_mode == "playlist":
            return "Playlist"
        if self.repeat_mode == "track":
            return "Track"
        return "None"

    def update_repeat_button(self):
        active_style = (
            "color: rgba(255,255,255,230); "
            "background: rgba(255,139,216,32); "
            "border: 1px solid rgba(255,139,216,72);"
        )
        off_style = (
            "color: rgba(255,255,255,230); "
            "background: rgba(255,255,255,38); "
            "border: 1px solid rgba(255,255,255,28);"
        )

        if self.repeat_mode == "playlist":
            self.repeat_btn.setText("↻")
            self.repeat_btn.setToolTip("Boucle playlist")
            self.repeat_btn.setChecked(True)
            self.repeat_btn.setStyleSheet(active_style)
        elif self.repeat_mode == "track":
            self.repeat_btn.setText("↻1")
            self.repeat_btn.setToolTip("Boucle du morceau")
            self.repeat_btn.setChecked(True)
            self.repeat_btn.setStyleSheet(active_style)
        else:
            self.repeat_btn.setText("↻")
            self.repeat_btn.setToolTip("Boucle désactivée")
            self.repeat_btn.setChecked(False)
            self.repeat_btn.setStyleSheet(off_style)


    def set_repeat_mode(self, mode: str):
        if mode not in {"playlist", "track", "off"}:
            mode = "playlist"
        self.repeat_mode = mode
        self.repeat_enabled = mode != "off"
        self.update_repeat_button()
        self.notify_mpris()

    def set_repeat(self, enabled: bool):
        self.set_repeat_mode("playlist" if enabled else "off")

    def connect_player(self):
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.playbackStateChanged.connect(self.update_play_button)
        self.player.mediaStatusChanged.connect(self.on_media_status)

    def load_library(self):
        self.tracks.clear()

        if not LIBRARY_FILE.exists():
            return

        try:
            data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, list):
            return

        seen = set()

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                path = Path(item.get("path", "")).expanduser().resolve()
            except Exception:
                continue

            if (
                not path.exists()
                or not path.is_file()
                or path.name.startswith(".")
                or is_hidden_path(path)
                or path.suffix.lower() not in AUDIO_EXTENSIONS
            ):
                continue

            key = str(path)
            if key in seen:
                continue

            seen.add(key)
            # V28 :
            # Les titres sauvegardés dans library.json peuvent venir d'anciennes versions
            # qui remplaçaient les "-" par des espaces. Comme l'app n'a pas encore
            # d'édition manuelle des métadonnées, on reconstruit le titre depuis le nom
            # du fichier à chaque chargement pour restaurer les tirets partout.
            self.tracks.append(
                Track(
                    path=path,
                    title=clean_title(path),
                    artist=item.get("artist") or "",
                    album=item.get("album") or "",
                    playlist=item.get("playlist") or "Bibliothèque",
                    source_root=item.get("source_root") or "",
                    duration_ms=int(item.get("duration_ms") or 0),
                )
            )

        self.recover_sources_from_existing_library()
        self.sort_tracks_alphabetically()
        self.save_library()

    def save_library(self):
        try:
            APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "path": str(track.path),
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "playlist": track.playlist,
                    "source_root": track.source_root,
                    "duration_ms": int(track.duration_ms or 0),
                }
                for track in self.tracks
                if track.path.exists()
            ]
            LIBRARY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load_sources(self):
        self.folder_sources = []

        if not SOURCES_FILE.exists():
            return

        try:
            data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, list):
            return

        seen = set()

        for value in data:
            try:
                path = Path(str(value)).expanduser().resolve()
            except Exception:
                continue

            if not path.exists() or not path.is_dir() or is_hidden_path(path):
                continue

            key = str(path)
            if key in seen:
                continue

            seen.add(key)
            self.folder_sources.append(path)

    def save_sources(self):
        try:
            APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = [str(path) for path in self.folder_sources if path.exists() and path.is_dir()]
            SOURCES_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def recover_sources_from_existing_library(self):
        """
        V34 : si l'app a été utilisée avant sources.json, les playlists existaient
        mais leurs dossiers n'étaient pas forcément enregistrés comme sources.
        On récupère donc les dossiers depuis :
        1) track.source_root quand il existe ;
        2) le dossier commun des morceaux d'une même playlist.
        """
        changed = False
        known = {str(path) for path in self.folder_sources}

        def add_source(path: Path) -> bool:
            try:
                path = path.expanduser().resolve()
            except Exception:
                return False

            if not path.exists() or not path.is_dir() or is_hidden_path(path):
                return False

            key = str(path)
            if key in known:
                return False

            known.add(key)
            self.folder_sources.append(path)
            return True

        for track in self.tracks:
            if not track.source_root:
                continue

            if add_source(Path(track.source_root)):
                changed = True

        by_playlist: dict[str, list[Track]] = {}

        for track in self.tracks:
            if track.source_root:
                continue

            if not track.playlist or track.playlist in {"Bibliothèque", "Ajout manuel"}:
                continue

            by_playlist.setdefault(track.playlist, []).append(track)

        for playlist, tracks in by_playlist.items():
            existing_paths = [track.path for track in tracks if track.path.exists()]

            if not existing_paths:
                continue

            candidate = None

            # Priorité : retrouver un parent dont le nom correspond exactement à la playlist.
            for path in existing_paths:
                for parent in [path.parent, *path.parents]:
                    if parent.name == playlist and parent.exists() and parent.is_dir():
                        candidate = parent
                        break
                if candidate is not None:
                    break

            # Fallback : dossier commun contenant les morceaux de cette playlist.
            if candidate is None:
                try:
                    candidate = Path(os.path.commonpath([str(path.parent) for path in existing_paths]))
                except Exception:
                    candidate = existing_paths[0].parent

            try:
                candidate = candidate.expanduser().resolve()
            except Exception:
                continue

            if not candidate.exists() or not candidate.is_dir() or is_hidden_path(candidate):
                continue

            candidate_key = str(candidate)

            if add_source(candidate):
                changed = True

            # Lie les morceaux déjà présents à la source retrouvée pour que les suppressions
            # soient détectées au prochain rescan.
            for track in tracks:
                try:
                    resolved_track = track.path.expanduser().resolve()
                    if resolved_track == candidate or candidate in resolved_track.parents:
                        track.source_root = candidate_key
                        changed = True
                except Exception:
                    continue

        if changed:
            self.folder_sources.sort(key=lambda path: path.name.casefold())
            self.save_sources()

    def scan_audio_folder(self, root: Path) -> list[Path]:
        paths = []

        try:
            root = root.expanduser().resolve()
        except Exception:
            return paths

        if not root.exists() or not root.is_dir() or is_hidden_path(root):
            return paths

        for current_root, dirs, files in __import__("os").walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                if filename.startswith("."):
                    continue

                path = Path(current_root) / filename

                if path.suffix.lower() in AUDIO_EXTENSIONS and not is_hidden_path(path):
                    paths.append(path)

        return sorted(paths, key=lambda p: clean_title(p).casefold())

    def remember_folder_source(self, folder: Path):
        try:
            folder = folder.expanduser().resolve()
        except Exception:
            return

        if not folder.exists() or not folder.is_dir() or is_hidden_path(folder):
            return

        if all(str(existing) != str(folder) for existing in self.folder_sources):
            self.folder_sources.append(folder)
            self.folder_sources.sort(key=lambda p: p.name.casefold())
            self.save_sources()

    def rescan_saved_folders(self, initial=False):
        if not self.folder_sources:
            return

        changed = False
        existing_manual = [track for track in self.tracks if not track.source_root]
        known_durations = {str(track.path.resolve()): int(track.duration_ms or 0) for track in self.tracks if track.path.exists()}
        synced_tracks = []
        seen = {str(track.path.resolve()) for track in existing_manual if track.path.exists()}

        valid_sources = []

        for root in self.folder_sources:
            try:
                root = root.expanduser().resolve()
            except Exception:
                changed = True
                continue

            if not root.exists() or not root.is_dir() or is_hidden_path(root):
                changed = True
                continue

            valid_sources.append(root)
            playlist = root.name or "Dossier"

            for path in self.scan_audio_folder(root):
                key = str(path.resolve())
                if key in seen:
                    continue

                seen.add(key)
                synced_tracks.append(
                    Track(
                        path=path,
                        title=clean_title(path),
                        playlist=playlist,
                        source_root=str(root),
                        duration_ms=known_durations.get(key, 0),
                    )
                )

        new_tracks = existing_manual + synced_tracks
        old_signature = [(str(t.path), t.title, t.playlist, t.source_root, t.path.exists()) for t in self.tracks]
        new_signature = [(str(t.path), t.title, t.playlist, t.source_root, t.path.exists()) for t in new_tracks]

        if old_signature != new_signature:
            changed = True

        if [str(p) for p in valid_sources] != [str(p) for p in self.folder_sources]:
            changed = True
            self.folder_sources = valid_sources
            self.save_sources()

        if changed:
            current_path = None
            if self.current_index is not None and 0 <= self.current_index < len(self.tracks):
                current_path = self.tracks[self.current_index].path

            self.tracks = new_tracks
            self.sort_tracks_alphabetically()

            if current_path is not None:
                self.current_index = None
                for i, track in enumerate(self.tracks):
                    if track.path == current_path:
                        self.current_index = i
                        break

            self.save_library()
            self.refresh_all()
            self.queue_missing_durations()


    def queue_missing_durations(self):
        """V54 : désactivé en mode grosses playlists pour éviter ffprobe en boucle."""
        return

    def read_duration_with_ffprobe(self, path: Path) -> int:
        """Retourne la durée en millisecondes avec ffprobe, ou 0 si impossible."""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0

        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
            )
        except Exception:
            return 0

        try:
            seconds = float((result.stdout or "").strip())
        except Exception:
            return 0

        if seconds <= 0:
            return 0
        return int(seconds * 1000)

    def scan_next_duration(self):
        """Scanne une seule durée à la fois pour éviter de bloquer l'app."""
        if self.duration_scan_running:
            return

        while self.duration_scan_queue:
            index = self.duration_scan_queue.pop(0)
            if not (0 <= index < len(self.tracks)):
                continue

            track = self.tracks[index]
            if track.duration_ms or not track.path.exists():
                continue

            self.duration_scan_running = True
            duration_ms = self.read_duration_with_ffprobe(track.path)
            self.duration_scan_running = False

            if duration_ms:
                track.duration_ms = duration_ms
                self.save_library()
                self.refresh_table()
            return


    def refresh_all(self):
        self.refresh_sidebar()
        self.refresh_table()

    def refresh_sidebar(self):
        current = self.current_playlist
        self.sidebar.blockSignals(True)
        self.sidebar.clear()

        playlists = sorted({
            t.playlist
            for t in self.tracks
            if t.playlist and t.playlist != "Bibliothèque"
        })

        for name in playlists:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setIcon(themed_icon("folder-music", "folder"))
            self.sidebar.addItem(item)

        row = -1
        if current in playlists:
            row = playlists.index(current)
        elif playlists:
            row = 0
            self.current_playlist = playlists[0]
        else:
            self.current_playlist = ""

        self.sidebar.setCurrentRow(row)
        self.sidebar.blockSignals(False)

    def on_sidebar_changed(self, row: int):
        item = self.sidebar.item(row)
        self.current_playlist = item.data(Qt.ItemDataRole.UserRole) if item else ""
        self.refresh_table()

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Ajouter des morceaux",
            str(Path.home()),
            "Audio (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus *.aiff *.aif);;Tous les fichiers (*)",
        )
        if not files:
            return
        self.add_paths(sorted([Path(f) for f in files], key=lambda p: clean_title(p).casefold()), playlist="Ajout manuel")

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ajouter un dossier", str(Path.home()))
        if not folder:
            return

        root = Path(folder)
        self.remember_folder_source(root)
        paths = self.scan_audio_folder(root)
        self.add_paths(paths, playlist=root.name or "Dossier", source_root=str(root.expanduser().resolve()))
        self.rescan_saved_folders()

    def add_paths(self, paths: list[Path], playlist: str, source_root: str = ""):
        existing = {str(t.path.resolve()) for t in self.tracks if t.path.exists()}
        added = 0
        for path in paths:
            try:
                path = path.expanduser().resolve()
            except Exception:
                continue
            if not path.exists() or not path.is_file():
                continue
            if path.name.startswith(".") or is_hidden_path(path):
                continue
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            key = str(path)
            if key in existing:
                continue
            self.tracks.append(Track(path=path, title=clean_title(path), playlist=playlist, source_root=source_root, duration_ms=0))
            existing.add(key)
            added += 1
        if added:
            self.sort_tracks_alphabetically()
            self.current_playlist = playlist if playlist else ""
            self.save_library()
        self.refresh_all()
        if added:
            self.queue_missing_durations()

    def sort_tracks_alphabetically(self):
        current_path = None
        if self.current_index is not None and 0 <= self.current_index < len(self.tracks):
            current_path = self.tracks[self.current_index].path

        self.tracks.sort(
            key=lambda track: (
                track.title.casefold(),
                track.artist.casefold(),
                track.album.casefold(),
                str(track.path).casefold(),
            )
        )

        if current_path is not None:
            for i, track in enumerate(self.tracks):
                if track.path == current_path:
                    self.current_index = i
                    break

    def clear_library(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.tracks.clear()
        self.folder_sources.clear()
        self.save_sources()
        self.current_index = None
        self.current_playlist = ""
        self.now_title.setText("Aucun morceau")
        self.now_subtitle.setText("Ajoute des fichiers ou un dossier pour commencer")
        self.save_library()
        self.refresh_all()

    def tracks_for_view(self) -> list[int]:
        query = self.search.text().strip().lower()
        result = []

        if not self.current_playlist:
            return result

        for i, track in enumerate(self.tracks):
            if track.playlist != self.current_playlist:
                continue
            haystack = " ".join([track.title, track.artist, track.album, track.playlist, track.path.name]).lower()
            if query and query not in haystack:
                continue
            result.append(i)
        return result

    def refresh_table(self):
        self.filtered_indices = self.tracks_for_view()
        if hasattr(self, "table_model"):
            self.table_model.layoutChanged.emit()

    def selected_track_index(self) -> int | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        row = selected[0].row()
        if not (0 <= row < len(self.filtered_indices)):
            return None
        return self.filtered_indices[row]

    def play_clicked_row(self, model_index):
        row = model_index.row()
        if 0 <= row < len(self.filtered_indices):
            self.play_track(self.filtered_indices[row])

    def play_selected_row(self):
        index = self.selected_track_index()
        if index is not None:
            self.play_track(index)

    def play_track(self, index: int):
        if not (0 <= index < len(self.tracks)):
            return
        track = self.tracks[index]
        self.current_index = index
        self.player.setSource(QUrl.fromLocalFile(str(track.path)))
        self.player.play()
        self.now_title.setText(track.title)
        subtitle = track.artist or track.album or track.playlist or track.path.parent.name
        self.now_subtitle.setText(subtitle)
        self.highlight_current_track()
        self.notify_mpris()

    def highlight_current_track(self):
        if hasattr(self, "table_model"):
            self.table_model.layoutChanged.emit()
        self.table.clearSelection()
        self.table.setCurrentIndex(QModelIndex())

    def toggle_play(self):
        if self.player.source().isEmpty():
            index = self.selected_track_index()
            if index is None and self.filtered_indices:
                index = self.filtered_indices[0]
            if index is not None:
                self.play_track(index)
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_shuffle(self):
        self.set_shuffle(self.shuffle_btn.isChecked())

    def toggle_repeat(self):
        if self.repeat_mode == "off":
            self.set_repeat_mode("playlist")
        elif self.repeat_mode == "playlist":
            self.set_repeat_mode("track")
        else:
            self.set_repeat_mode("off")

    def previous_track(self):
        if not self.filtered_indices:
            return
        if self.current_index not in self.filtered_indices:
            self.play_track(self.filtered_indices[0])
            return
        pos = self.filtered_indices.index(self.current_index)
        if pos <= 0:
            if self.repeat_mode == "playlist":
                self.play_track(self.filtered_indices[-1])
            else:
                self.play_track(self.filtered_indices[0])
            return
        self.play_track(self.filtered_indices[pos - 1])

    def next_track(self, autoplay_end=False):
        if not self.filtered_indices:
            return
        if self.current_index not in self.filtered_indices:
            self.play_track(self.filtered_indices[0])
            return

        if autoplay_end and self.repeat_mode == "track":
            self.play_track(self.current_index)
            return

        if self.shuffle_enabled and len(self.filtered_indices) > 1:
            choices = [idx for idx in self.filtered_indices if idx != self.current_index]
            self.play_track(random.choice(choices))
            return

        pos = self.filtered_indices.index(self.current_index)
        next_pos = pos + 1

        if next_pos >= len(self.filtered_indices):
            if self.repeat_mode == "playlist":
                next_pos = 0
            elif autoplay_end:
                self.player.stop()
                return
            else:
                next_pos = len(self.filtered_indices) - 1

        self.play_track(self.filtered_indices[next_pos])

    def on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_track(autoplay_end=True)

    def update_play_button(self, state):
        self.play_btn.setText("❚❚" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")
        self.notify_mpris()

    def update_duration(self, duration):
        self.progress.setRange(0, max(0, duration))
        self.time_right.setText(self.format_time(duration))

    def update_position(self, position):
        if not self.user_is_sliding:
            self.progress.setValue(position)
        self.time_left.setText(self.format_time(position))

    def on_slider_pressed(self):
        self.user_is_sliding = True

    def on_slider_released(self):
        self.user_is_sliding = False
        self.player.setPosition(self.progress.value())

    def on_slider_moved(self, value):
        self.time_left.setText(self.format_time(value))

    @staticmethod
    def format_time(ms: int) -> str:
        seconds = max(0, int(ms / 1000))
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"


def main():
    # Important : ces variables doivent exister avant la création de QApplication
    # pour que KDE/Plasma Wayland regroupe la fenêtre avec le bon fichier .desktop.
    os.environ["QT_WAYLAND_APP_ID"] = APP_ID
    os.environ["QT_XCB_WINDOW_CLASS"] = APP_ID

    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_TITLE)
    app.setDesktopFileName(APP_ID)
    app.setOrganizationName("Princess")
    app.setOrganizationDomain("princess")
    app.setFont(QFont(UI_FONT, 10))

    window = PrincessITunes()
    window.setWindowTitle(APP_TITLE)

    # Force aussi l'icône de fenêtre si ton asset existe.
    icon_path = Path.home() / "Applications/Princess_iTunes/assets/icon.png"
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
        app.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    app.setDesktopFileName(APP_ID)
    set_x11_wm_class(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
