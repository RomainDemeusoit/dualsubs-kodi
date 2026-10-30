"""DualSubs Kodi 21 prototype. Requires an ffmpeg executable on PATH."""
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

import xbmc
import xbmcaddon
import xbmcgui


ADDON = xbmcaddon.Addon()
PLAYER = xbmc.Player()


def rpc(method, params):
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    response = json.loads(xbmc.executeJSONRPC(request))
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Kodi JSON-RPC error"))
    return response.get("result", {})


def get_subtitle_streams():
    players = rpc("Player.GetActivePlayers", {})
    video = next((p for p in players if p.get("type") == "video"), None)
    if not video:
        raise RuntimeError("Aucune vidéo n'est en cours de lecture.")
    playerid = video["playerid"]
    item = rpc("Player.GetItem", {"playerid": playerid, "properties": ["file"]})
    props = rpc("Player.GetProperties", {"playerid": playerid, "properties": ["subtitles"]})
    active = props.get("subtitles", [])
    # Keep embedded streams only. Kodi may append externally loaded subtitle files.
    # FFmpeg's subtitle selector is an ordinal among embedded subtitle streams.
    tracks = []
    embedded_ordinal = 0
    for stream in active:
        if stream.get("isexternal", False):
            continue
        stream = dict(stream)
        stream["ffmpeg_ordinal"] = embedded_ordinal
        embedded_ordinal += 1
        tracks.append(stream)
    return playerid, item.get("item", {}).get("file", ""), tracks


def extract_track(media, stream_index, destination):
    ffmpeg = shutil.which("ffmpeg")
    # LibreELEC's official FFmpeg Tools add-on installs outside Kodi's PATH.
    if not ffmpeg:
        bundled = "/storage/.kodi/addons/tools.ffmpeg-tools/bin/ffmpeg"
        if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
            ffmpeg = bundled
    if not ffmpeg:
        raise RuntimeError("FFmpeg est introuvable. Installez l'extension officielle « FFmpeg Tools » depuis le dépôt LibreELEC, puis relancez DualSubs.")
    # JSON-RPC stream indices are container stream indices; only text codecs are accepted.
    command = [ffmpeg, "-nostdin", "-v", "error", "-y", "-progress", "pipe:1", "-nostats", "-i", media,
               "-map", "0:s:%d" % stream_index, "-c:s", "srt", destination]
    progress = xbmcgui.DialogProgress()
    progress.create("DualSubs", "Extraction du sous-titre secondaire…")
    error_output = tempfile.TemporaryFile()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_output, bufsize=1, universal_newlines=True)
    progress_queue = queue.Queue()

    def read_progress():
        try:
            for line in process.stdout:
                if line.startswith("out_time="):
                    progress_queue.put(line.split("=", 1)[1].strip())
        finally:
            process.stdout.close()

    reader = threading.Thread(target=read_progress, daemon=True)
    reader.start()
    monitor = xbmc.Monitor()
    started = time.monotonic()
    percent = 0
    total_seconds = max(PLAYER.getTotalTime(), 1.0)
    try:
        while process.poll() is None:
            elapsed = int(time.monotonic() - started)
            try:
                while True:
                    clock = progress_queue.get_nowait()
                    if clock and clock != "N/A":
                        hours, minutes, seconds = clock.split(":")
                        output_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                        percent = max(percent, min(99, int(output_seconds * 100 / total_seconds)))
            except queue.Empty:
                pass
            progress.update(percent, "Extraction en cours — %d%% — %d s écoulées" % (percent, elapsed))
            if progress.iscanceled() or monitor.abortRequested():
                process.kill()
                process.wait()
                raise RuntimeError("Extraction annulée. Relancez DualSubs si vous souhaitez réessayer.")
            if elapsed >= 900:
                process.kill()
                process.wait()
                raise RuntimeError("L'extraction dépasse 15 minutes. Le fichier est peut-être très volumineux ou lent à lire.")
            xbmc.sleep(500)
        process.wait()
        reader.join(timeout=2)
        error_output.seek(0)
        error = error_output.read()
        if process.returncode:
            raise RuntimeError(error.decode("utf-8", "replace")[-500:] or "Échec FFmpeg")
    finally:
        error_output.close()
        progress.close()


def read_srt(path):
    raw = open(path, "rb").read()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            pass
    return raw.decode("utf-8", "replace")


def timestamp(value):
    h, m, rest = value.replace(",", ".").split(":")
    sec, ms = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int((ms + "000")[:3]) / 1000.0


def parse_srt(text):
    events = []
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    for block in blocks:
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            continue
        left, right = [x.strip().split()[0] for x in lines[timing].split("-->", 1)]
        body = "\n".join(lines[timing + 1:]).strip()
        if body:
            events.append((timestamp(left), timestamp(right), body))
    return events


def show_overlay(events, playerid, expected_file, run_token):
    # Kodi's fullscreen video window is 12005. The current window can still
    # be the add-on/menu window when the script was launched from playback.
    window = xbmcgui.Window(12005)
    width, height = window.getWidth(), window.getHeight()
    # Place text in the upper letterbox area, with a little margin from the edge.
    # Use a font name present in Kodi's Estuary skin. Unknown names fall back
    # to the small default font, which made the previous font50 change invisible.
    x, y = int(width * .06), int(height * .04)
    control_width, control_height = int(width * .88), int(height * .12)
    font = "font60"
    # Kodi labels do not expose an outline option. Four black labels offset by
    # two pixels create a small outline behind the white foreground label.
    outline = []
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        shadow = xbmcgui.ControlLabel(x + dx, y + dy, control_width, control_height, "",
                                      font=font, textColor="0xFF000000", alignment=0x02 | 0x04)
        window.addControl(shadow)
        outline.append(shadow)
    label = xbmcgui.ControlLabel(x, y, control_width, control_height, "",
                                  font=font, textColor="0xFFFFFFFF", alignment=0x02 | 0x04)
    window.addControl(label)
    controls = outline + [label]
    monitor = xbmc.Monitor()
    try:
        while (not monitor.abortRequested() and PLAYER.isPlayingVideo()
               and window.getProperty("dualsubs.run") == run_token
               and PLAYER.getPlayingFile() == expected_file):
            # Kodi can keep playing audio/video in the background while the user
            # browses menus. Show the overlay only in fullscreen video playback.
            in_fullscreen_video = xbmcgui.getCurrentWindowId() == 12005
            for control in controls:
                control.setVisible(in_fullscreen_video)
            if in_fullscreen_video:
                current = PLAYER.getTime()
                active = next((text for start, end, text in events if start <= current < end), "")
            else:
                active = ""
            for control in controls:
                control.setLabel(active)
            if monitor.waitForAbort(0.15):
                break
    finally:
        try:
            window.removeControls(controls)
        except RuntimeError:
            pass
        if window.getProperty("dualsubs.run") == run_token:
            window.clearProperty("dualsubs.run")


def main():
    run_window = None
    run_token = None
    try:
        source_file = PLAYER.getPlayingFile()
        playerid, media, streams = get_subtitle_streams()
        if len(streams) < 2:
            raise RuntimeError("Kodi ne signale pas au moins deux pistes de sous-titres.")
        if len(streams) < 2:
            raise RuntimeError("Kodi ne signale pas au moins deux pistes intégrées au film.")
        labels = []
        for i, stream in enumerate(streams):
            language = stream.get("language") or "langue inconnue"
            codec = stream.get("codec") or "codec inconnu"
            name = stream.get("name") or ""
            labels.append("Piste %d — %s — %s%s" % (i + 1, language, codec, (" — " + name) if name else ""))
        first = xbmcgui.Dialog().select("Choisissez les sous-titres principaux — affichés en bas par Kodi", labels)
        if first < 0:
            return
        second_options = [label for i, label in enumerate(labels) if i != first]
        second = xbmcgui.Dialog().select("Choisissez les sous-titres secondaires — affichés en haut par DualSubs", second_options)
        if second < 0:
            return
        second = second if second < first else second + 1
        if PLAYER.getPlayingFile() != source_file:
            raise RuntimeError("Le film a changé pendant la sélection. Relancez DualSubs depuis le film souhaité.")
        # Replace any earlier overlay immediately, before FFmpeg starts reading
        # the media file. This prevents stale subtitles during a long extraction.
        run_window = xbmcgui.Window(12005)
        run_token = uuid.uuid4().hex
        run_window.setProperty("dualsubs.run", run_token)
        # Both APIs use the ordinal among subtitle streams.
        rpc("Player.SetSubtitle", {"playerid": playerid, "subtitle": streams[first]["index"], "enable": True})
        temp_dir = os.path.join(tempfile.gettempdir(), "dualsubs")
        os.makedirs(temp_dir, exist_ok=True)
        subtitle_file = os.path.join(temp_dir, "secondary-%s.srt" % uuid.uuid4().hex)
        extract_track(media, streams[second]["ffmpeg_ordinal"], subtitle_file)
        try:
            if PLAYER.getPlayingFile() != source_file:
                raise RuntimeError("Le film a changé pendant l'extraction. Relancez DualSubs depuis le film souhaité.")
            events = parse_srt(read_srt(subtitle_file))
            if not events:
                raise RuntimeError("FFmpeg a terminé, mais la piste choisie n'a produit aucun sous-titre lisible. Essayez une autre piste textuelle.")
            xbmcgui.Dialog().notification("DualSubs", "Deuxième piste chargée (%d sous-titres)." % len(events))
            show_overlay(events, playerid, source_file, run_token)
        finally:
            try:
                os.remove(subtitle_file)
            except OSError:
                pass
    except Exception as exc:
        xbmcgui.Dialog().ok("DualSubs — prototype", str(exc))
    finally:
        if run_window and run_token and run_window.getProperty("dualsubs.run") == run_token:
            run_window.clearProperty("dualsubs.run")


main()
