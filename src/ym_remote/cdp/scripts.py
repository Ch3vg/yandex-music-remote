"""Скрипты страницы. Значения подставляются как JSON, не через format."""

from __future__ import annotations

import json

HELPERS = r"""
const ymSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
function ymVisible(el, min) {
  const need = min == null ? 2 : min;
  if (!el || !el.isConnected) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < need || rect.height < need) return false;
  const style = getComputedStyle(el);
  return style.display !== "none" && style.visibility !== "hidden";
}
function ymById(id, root) {
  const scope = root || document;
  if (!scope || !scope.querySelector) return null;
  return scope.querySelector('[data-test-id="' + id + '"]');
}
function ymClick(el) {
  if (!el) return false;
  el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
  el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  if (typeof el.click === "function") el.click();
  return true;
}
function ymSetNativeValue(el, value) {
  const node = el && el.matches && el.matches("input,textarea") ? el : (el && el.querySelector ? el.querySelector("input,textarea") : null);
  if (!node) return false;
  const proto = node instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  if (desc && desc.set) desc.set.call(node, value);
  else node.value = value;
  node.dispatchEvent(new Event("input", { bubbles: true }));
  node.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}
function ymRoots() {
  const ids = ["FULLSCREEN_PLAYER_MODAL", "PLAYERBAR_DESKTOP", "VIBE_PLAYERBAR"];
  const roots = [];
  for (const id of ids) {
    const el = ymById(id);
    if (el) roots.push(el);
  }
  roots.push(document.body);
  return roots;
}
function ymText(el) {
  if (!el) return "";
  const chunks = [];
  const walk = (node) => {
    if (!node) return;
    if (node.nodeType === 3) {
      chunks.push(node.nodeValue || "");
      return;
    }
    if (node.nodeType !== 1 || node.getAttribute("aria-hidden") === "true") return;
    if (node.classList && node.classList.contains("rfm-marquee-container")) {
      const once = node.querySelector(".rfm-child");
      if (once) { walk(once); return; }
    }
    for (const child of node.childNodes) walk(child);
  };
  walk(el);
  return chunks.join("").trim();
}
function ymUsableArtUrl(raw) {
  if (!raw) return "";
  let url = String(raw).trim().replace(/^['"]|['"]$/g, "");
  if (!url || /^blob:/i.test(url)) return "";
  if (/^data:/i.test(url)) {
    if (url.length > 24000 || !/^data:image\//i.test(url)) return "";
    return url;
  }
  if (url.startsWith("//")) url = "https:" + url;
  if (/^https?:\/\//i.test(url)) return url;
  return "";
}
function ymFirstArtUrl(value) {
  const text = String(value || "");
  const re = /url\(\s*(['"]?)([^)'"]*)\1\s*\)/gi;
  let match;
  while ((match = re.exec(text))) {
    const url = ymUsableArtUrl(match[2]);
    if (url) return url;
  }
  return "";
}
function ymCardArt(node) {
  const empty = { cover: "", background: "" };
  if (!node) return empty;
  const imgs = node.matches && node.matches("img") ? [node] : Array.from(node.querySelectorAll("img"));
  for (const img of imgs) {
    const url = ymUsableArtUrl(img.currentSrc || img.getAttribute("src") || "");
    if (url) return { cover: url, background: "" };
  }
  const nodes = [node].concat(Array.from(node.querySelectorAll("*"))).slice(0, 24);
  for (const el of nodes) {
    let image = "";
    const inline = (el.getAttribute && el.getAttribute("style")) || "";
    try { image = getComputedStyle(el).backgroundImage || ""; } catch (e) { image = ""; }
    const url = ymFirstArtUrl(image) || ymFirstArtUrl(inline);
    if (url) return { cover: url, background: "" };
  }
  let image = "";
  let color = "";
  const inline = (node.getAttribute && node.getAttribute("style")) || "";
  try {
    const style = getComputedStyle(node);
    image = style.backgroundImage || "";
    color = style.backgroundColor || "";
  } catch (e) {}
  const candidate = [image, inline, color].find((part) => {
    if (!part || part === "none" || part === "transparent" || part === "rgba(0, 0, 0, 0)") return false;
    if (/blob:/i.test(part) || /url\(\s*['"]?\s*['"]?\s*\)/i.test(part)) return false;
    return /gradient\(|background|^#|rgb\(|hsl\(/i.test(part) && part.length < 2000;
  });
  return { cover: "", background: candidate || "" };
}
function ymFindRepeat() {
  const full = ymById("FULLSCREEN_PLAYER_MODAL");
  if (full && ymVisible(full)) {
    const inside = ymFindRepeatIn(full);
    if (inside) return inside;
  }
  const bar = ymById("PLAYERBAR_DESKTOP");
  if (bar) return ymFindRepeatIn(bar);
  return null;
}
function ymFindRepeatIn(root) {
  const buttons = root.querySelectorAll('[data-test-id^="REPEAT_BUTTON"]');
  for (const button of buttons) {
    if (ymVisible(button) && !ymInTrackRow(button)) return button;
  }
  return null;
}
function ymInTrackRow(el) {
  return !!(el && el.closest && el.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]'));
}
function ymLikeActive(id, pressed, checked) {
  if (!id || !id.startsWith("LIKE_BUTTON")) return false;
  if (id.includes("_ON") || id.includes("_ACTIVE") || id.includes("_LIKED")) return true;
  return pressed === "true" || checked === "true";
}
function ymFindControl(prefix) {
  for (const root of ymRoots()) {
    const buttons = root.querySelectorAll("[data-test-id]");
    for (const button of buttons) {
      const id = button.getAttribute("data-test-id") || "";
      if (!id.startsWith(prefix) || !ymVisible(button) || ymInTrackRow(button)) continue;
      return button;
    }
  }
  return null;
}
function ymFindReaction(kind) {
  const like = kind === "like";
  for (const root of ymRoots()) {
    const buttons = root.querySelectorAll("[data-test-id]");
    for (const button of buttons) {
      const id = button.getAttribute("data-test-id") || "";
      const match = like ? id.startsWith("LIKE_BUTTON") : (id === "DISLIKE_BUTTON" || id.includes("DISLIKE_BUTTON"));
      if (!match || !ymVisible(button) || ymInTrackRow(button)) continue;
      return button;
    }
  }
  return null;
}
function ymControlOn(button) {
  if (!button) return false;
  const id = button.getAttribute("data-test-id") || "";
  if (id.startsWith("LIKE_BUTTON")) return ymLikeActive(id, button.getAttribute("aria-pressed"), button.getAttribute("aria-checked"));
  return id.endsWith("_ON") || id.includes("_ACTIVE") || id.includes("_LIKED") || button.getAttribute("aria-pressed") === "true" || button.getAttribute("aria-checked") === "true";
}
function ymTransportPlaying() {
  for (const root of ymRoots()) {
    if (root === document.body) continue;
    const buttons = root.querySelectorAll('[data-test-id="PAUSE_BUTTON"], [aria-label="Пауза"]');
    for (const button of buttons) {
      if (ymVisible(button) && !ymInTrackRow(button)) return true;
    }
  }
  return false;
}
function ymPressEscape() {
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
}
async function ymInAppGo(path) {
  let dest = null;
  try { dest = new URL(path, location.href); } catch (error) { return false; }
  const target = dest.pathname + dest.search + dest.hash;
  const here = () => location.pathname + location.search + location.hash;
  if (here() === target) return true;
  const router = window.next && window.next.router;
  if (router && typeof router.push === "function") {
    try {
      const pending = router.push(target);
      if (pending && typeof pending.then === "function") await pending;
    } catch (error) {}
    for (let tick = 0; tick < 15 && here() !== target; tick++) await ymSleep(40);
    if (here() === target) return true;
  }
  const root = document.body || document.documentElement;
  const anchor = document.createElement("a");
  anchor.setAttribute("href", path);
  root.appendChild(anchor);
  const blockProtocol = (event) => {
    let clicked = null;
    try { clicked = new URL(anchor.getAttribute("href") || path, location.href); } catch (error) { return; }
    if (clicked.protocol === "music-application:") event.preventDefault();
  };
  document.addEventListener("click", blockProtocol, true);
  ymClick(anchor);
  document.removeEventListener("click", blockProtocol, true);
  anchor.remove();
  await ymSleep(30);
  if (here() === target) return true;
  if (location.protocol === "music-application:" || dest.protocol === "music-application:") {
    const before = here();
    history.pushState(history.state, "", target);
    window.dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
    await ymSleep(50);
    return here() === target && here() !== before;
  }
  location.assign(path);
  return true;
}
function ymArtistIdFromHref(href) {
  if (!href) return null;
  try {
    const url = new URL(href, location.href);
    const q = url.searchParams.get("artistId");
    if (q && /^\d+$/.test(q)) return Number(q);
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("artist");
    if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return Number(parts[at + 1]);
  } catch (error) {}
  const match = String(href).match(/(?:artistId=|\/artist\/)(\d+)/);
  return match ? Number(match[1]) : null;
}
function ymReadArtistRefs(scope) {
  if (!scope || !scope.querySelectorAll) return [];
  const refs = [];
  const seen = new Set();
  const pushRef = (name, id) => {
    const clean = (name || "").trim();
    if (!clean) return;
    const key = (id != null ? String(id) : "") + "|" + clean;
    if (seen.has(key)) return;
    seen.add(key);
    refs.push({ id: id != null ? id : null, name: clean });
  };
  const blocks = scope.querySelectorAll('[data-test-id="SEPARATED_ARTIST_TITLE"]');
  for (const block of blocks) {
    const links = block.querySelectorAll('a[href*="artist"]');
    if (links.length) {
      for (const link of links) {
        pushRef(ymText(link), ymArtistIdFromHref(link.getAttribute("href") || link.href));
      }
    } else if (block.matches && block.matches("a[href]")) {
      pushRef(ymText(block), ymArtistIdFromHref(block.getAttribute("href") || block.href));
    } else {
      const anyLink = block.querySelector("a[href]");
      const id = anyLink ? ymArtistIdFromHref(anyLink.getAttribute("href") || anyLink.href) : null;
      pushRef(ymText(block), id);
    }
  }
  if (!refs.length) {
    for (const link of scope.querySelectorAll('a[href*="artist"]')) {
      pushRef(ymText(link), ymArtistIdFromHref(link.getAttribute("href") || link.href));
    }
  }
  return refs;
}
"""


def script(body: str) -> str:
    return "(async () => {\n" + HELPERS + "\n" + body + "\n})()"


def fill(body: str, **values: object) -> str:
    for key, value in values.items():
        body = body.replace(f"__{key}__", json.dumps(value, ensure_ascii=False))
    return script(body)


def read_bar_script() -> str:
    return script(
        r"""
const bar = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || ymById("VIBE_PLAYERBAR") || document.body;
let title = ymText(ymById("TRACK_TITLE", bar)) || ymText(ymById("VIBE_PLAYERBAR_TRACK_NAME"));
const artistRoot = ymById("VIBE_DYNAMIC_ARTISTS") || ymById("PLAYERBAR_DESKTOP") || bar;
let artists = Array.from(artistRoot.querySelectorAll('[data-test-id="SEPARATED_ARTIST_TITLE"]')).map((el) => ymText(el)).filter(Boolean);
let cover = "";
const vibeCover = ymById("VIBE_ALBUM_COVER");
const coverRoot = (vibeCover && vibeCover.querySelector("img")) || ymById("ENTITY_COVER_IMAGE", bar);
if (coverRoot) {
  const img = coverRoot.matches && coverRoot.matches("img") ? coverRoot : coverRoot.querySelector("img");
  const node = img || coverRoot;
  cover = node.currentSrc || node.getAttribute("src") || "";
}
let isPlaying = ymTransportPlaying();
if (navigator.mediaSession && navigator.mediaSession.metadata) {
  const meta = navigator.mediaSession.metadata;
  if (!title) {
    title = meta.title || "";
    isPlaying = navigator.mediaSession.playbackState === "playing";
  }
  if (!artists.length && meta.artist) artists = meta.artist.split(",").map((name) => name.trim()).filter(Boolean);
  if (!cover && meta.artwork && meta.artwork.length) {
    const art = meta.artwork[meta.artwork.length - 1];
    cover = (art && art.src) || "";
  }
}
if (!title) return null;
let volume = null;
const volumeSlider = ymById("CHANGE_VOLUME_SLIDER");
if (volumeSlider) {
  const max = Number(volumeSlider.max);
  const denom = max > 0 ? max : 100;
  volume = Math.round(Number(volumeSlider.value || 0) / denom * 100);
}
let position = null;
let duration = null;
const timeSlider = ymById("TIMECODE_SLIDER");
if (timeSlider && timeSlider.value !== "") {
  position = Number(timeSlider.value);
  duration = timeSlider.max === "" ? null : Number(timeSlider.max);
}
if (!Number.isFinite(position) || !Number.isFinite(duration)) {
  const toSec = (text) => {
    const match = String(text || "").trim().match(/^(?:(\d+):)?(\d+):(\d+)$/);
    if (!match) return null;
    return (match[1] ? Number(match[1]) : 0) * 3600 + Number(match[2]) * 60 + Number(match[3]);
  };
  const startSec = toSec(ymText(ymById("TIMECODE_TIME_START")));
  const endSec = toSec(ymText(ymById("TIMECODE_TIME_END")));
  if (startSec != null && endSec != null) {
    position = startSec;
    duration = endSec;
  }
}
let repeatMode = "off";
const repeat = ymFindRepeat();
if (repeat) {
  const id = repeat.getAttribute("data-test-id") || "";
  if (id === "REPEAT_BUTTON_REPEAT_ONE") repeatMode = "one";
  else if (id === "REPEAT_BUTTON_REPEAT_CONTEXT") repeatMode = "queue";
}
let shuffle = false;
const shuffleButton = ymFindControl("SHUFFLE_BUTTON");
if (shuffleButton) {
  const id = shuffleButton.getAttribute("data-test-id") || "";
  shuffle = id.endsWith("_ON") || shuffleButton.getAttribute("aria-pressed") === "true";
}
const likeButton = ymFindControl("LIKE_BUTTON");
const liked = likeButton ? ymLikeActive(likeButton.getAttribute("data-test-id") || "", likeButton.getAttribute("aria-pressed"), likeButton.getAttribute("aria-checked")) : false;
let artistHref = null;
const artistLink = artistRoot.querySelector('[data-test-id="SEPARATED_ARTIST_TITLE"] a, a[href*="artist"]');
if (artistLink) artistHref = artistLink.href || null;
let artistRefs = ymReadArtistRefs(artistRoot);
if (!artistRefs.length && artists.length) {
  artistRefs = artists.map((name) => ({ id: null, name }));
}
let albumHref = null;
const coverBox = ymById("VIBE_ALBUM_COVER") || ymById("PLAYERBAR_DESKTOP_COVER_CONTAINER");
const albumLink = coverBox && coverBox.querySelector("a");
if (albumLink) albumHref = albumLink.href || null;
if (!albumHref) {
  const coverButton = ymById("ENTITY_COVER_BUTTON");
  if (coverButton && coverButton.href) albumHref = coverButton.href;
}
let queueName = "";
let contextLabel = "";
const playingSubtitle = ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_SUBTITLE"));
const playingTitle = ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_TITLE"));
if (playingTitle) queueName = playingTitle;
if (playingSubtitle && playingSubtitle.replace(/\s+/g, " ").trim().toLowerCase() !== "сейчас играет") {
  contextLabel = playingSubtitle;
}
const nameIds = ["FULLSCREEN_PLAYER_CONTEXT_TITLE", "FULLSCREEN_PLAYER_HEADER_TITLE", "PLAYER_CONTEXT_TITLE", "CONTEXT_TITLE"];
const modal = ymById("FULLSCREEN_PLAYER_MODAL");
if (!queueName) {
  for (const id of nameIds) {
    const el = (modal && ymById(id, modal)) || ymById(id);
    if (el && ymText(el)) { queueName = ymText(el); break; }
  }
}
if (!queueName) {
  const reset = ymById("RESET_VIBE_CONTEXT_BUTTON");
  const named = reset && reset.querySelector("[title]");
  const titled = named && named.getAttribute("title");
  if (titled && titled.trim()) queueName = titled.trim();
}
if (!queueName) {
  const scope = ymById("VIBE_PLAYERBAR") || ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL");
  const links = scope ? scope.querySelectorAll('a[href*="playlist"], a[href*="album"], a[href*="artist"]') : [];
  for (const link of links) {
    const value = ymText(link);
    if (value && value.length < 100) { queueName = value; break; }
  }
}
if (!queueName) {
  queueName = ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_TITLE")) || ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_SUBTITLE"));
}
return {
  title, artists, artist_refs: artistRefs, cover_url: cover || null, is_playing: isPlaying, volume,
  position_sec: position, duration_sec: duration, repeat_mode: repeatMode,
  shuffle, liked, artist_href: artistHref, album_href: albumHref, queue_name: queueName, context_label: contextLabel
};
"""
    )


def play_pause_script() -> str:
    return script(
        r"""
for (const root of ymRoots()) {
  const pause = ymById("PAUSE_BUTTON", root);
  const play = ymById("PLAY_BUTTON", root);
  const button = pause && ymVisible(pause) ? pause : (play && ymVisible(play) ? play : null);
  if (button) { ymClick(button); return true; }
}
return false;
"""
    )


def next_script() -> str:
    return script(
        r"""
const bar = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || ymById("VIBE_PLAYERBAR");
const scope = bar || document;
let button = ymById("NEXT_TRACK_BUTTON", scope) || scope.querySelector('[aria-label="Следующая песня"]');
if (!button) button = ymById("NEXT_TRACK_BUTTON") || document.querySelector('[aria-label="Следующая песня"]');
if (!button) return false;
ymClick(button);
return true;
"""
    )


def skip_queue_script(steps: int) -> str:
    """Кликает next/prev без сброса позиции и ждёт смены trackId между кликами."""
    return fill(
        r"""
const steps = __STEPS__;
const direction = steps < 0 ? -1 : 1;
const count = Math.abs(steps);
if (!Number.isFinite(count) || count < 1 || count > 40) return { ok: false, code: "too_far" };
function playerTrackId() {
  const scope = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || ymById("VIBE_PLAYERBAR");
  if (!scope || !scope.querySelectorAll) return "";
  const anchors = scope.querySelectorAll('a[href*="trackId="], a[href*="/track/"]');
  for (const anchor of anchors) {
    try {
      const url = new URL(anchor.href, location.href);
      const raw = url.searchParams.get("trackId");
      if (raw && /^\d+$/.test(raw)) return raw;
      const parts = url.pathname.split("/").filter(Boolean);
      const at = parts.lastIndexOf("track");
      if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return parts[at + 1];
    } catch (error) {}
  }
  return "";
}
function positionSec() {
  const slider = ymById("TIMECODE_SLIDER");
  const value = slider ? Number(slider.value) : NaN;
  return Number.isFinite(value) ? value : null;
}
function stepButton() {
  const id = direction > 0 ? "NEXT_TRACK_BUTTON" : "PREVIOUS_TRACK_BUTTON";
  const label = direction > 0 ? "Следующая песня" : "Предыдущая песня";
  const scope = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || ymById("VIBE_PLAYERBAR") || document;
  let button = ymById(id, scope) || scope.querySelector('[aria-label="' + label + '"]');
  if (!button) button = ymById(id) || document.querySelector('[aria-label="' + label + '"]');
  return button;
}
let seen = playerTrackId();
for (let index = 0; index < count; index++) {
  const button = stepButton();
  if (!button) return { ok: false, code: "fail" };
  const before = positionSec();
  ymClick(button);
  let changed = false;
  for (let tick = 0; tick < 40; tick++) {
    await ymSleep(100);
    const now = playerTrackId();
    if (now && now !== seen) {
      seen = now;
      changed = true;
      break;
    }
  }
  if (!changed) return { ok: false, code: "fail" };
  let stable = 0;
  let heard = false;
  for (let tick = 0; tick < 18; tick++) {
    await ymSleep(120);
    const now = playerTrackId();
    if (!now || now !== seen) {
      if (now) seen = now;
      stable = 0;
      heard = false;
      continue;
    }
    stable += 1;
    const pos = positionSec();
    if (pos != null && (pos < 1.5 || (before != null && Math.abs(pos - before) > 0.8))) heard = true;
    if (stable >= 5 && heard) break;
  }
}
return { ok: true, track_id: seen };
""",
        STEPS=steps,
    )


def previous_script() -> str:
    return script(
        r"""
const slider = ymById("TIMECODE_SLIDER");
if (slider) ymSetNativeValue(slider, "0");
await ymSleep(120);
const scope = ymById("PLAYERBAR_DESKTOP") || document;
let button = ymById("PREVIOUS_TRACK_BUTTON", scope) || scope.querySelector('[aria-label="Предыдущая песня"]');
if (!button) button = ymById("PREVIOUS_TRACK_BUTTON") || document.querySelector('[aria-label="Предыдущая песня"]');
if (!button) return false;
ymClick(button);
return true;
"""
    )


def volume_script(value: int) -> str:
    return fill(
        r"""
const slider = ymById("CHANGE_VOLUME_SLIDER");
if (!slider) return false;
const max = Number(slider.max);
const denom = max > 0 ? max : 100;
const next = (__VALUE__ / 100) * denom;
return ymSetNativeValue(slider, String(next));
""",
        VALUE=value,
    )


def seek_script(position: int) -> str:
    return fill(
        r"""
const slider = ymById("TIMECODE_SLIDER");
if (!slider) return false;
const max = Number(slider.max || 0);
let next = Number(__POSITION__);
if (!Number.isFinite(next) || next < 0) next = 0;
if (max && next > max) next = max;
return ymSetNativeValue(slider, String(next));
""",
        POSITION=position,
    )


def shuffle_script(on: bool) -> str:
    return fill(
        r"""
const button = ymFindControl("SHUFFLE_BUTTON");
if (!button) return false;
function ymShuffleOn(node) {
  if (!node) return false;
  const id = node.getAttribute("data-test-id") || "";
  return id.endsWith("_ON") || node.getAttribute("aria-pressed") === "true";
}
if (ymShuffleOn(button) === __ON__) return true;
ymClick(button);
for (let tick = 0; tick < 8; tick++) {
  await ymSleep(50);
  if (ymShuffleOn(ymFindControl("SHUFFLE_BUTTON")) === __ON__) return true;
}
return false;
""",
        ON=on,
    )


def cycle_repeat_script() -> str:
    return script(
        r"""
const button = ymFindRepeat();
if (!button) return "missing";
ymClick(button);
return "ok";
"""
    )


def set_repeat_script(mode: str) -> str:
    targets = {"off": "REPEAT_BUTTON_NO_REPEAT", "queue": "REPEAT_BUTTON_REPEAT_CONTEXT", "one": "REPEAT_BUTTON_REPEAT_ONE"}
    return fill(
        r"""
const target = __TARGET__;
for (let step = 0; step < 3; step++) {
  let button = ymFindRepeat();
  if (!button) return "missing";
  if (button.getAttribute("data-test-id") === target) return "ok";
  ymClick(button);
  await ymSleep(90);
  for (let check = 0; check < 12; check++) {
    button = ymFindRepeat();
    if (button && button.getAttribute("data-test-id") === target) return "ok";
    await ymSleep(50);
  }
}
return "fail";
""",
        TARGET=targets[mode],
    )


def reaction_script(kind: str) -> str:
    return fill(
        r"""
const kind = __KIND__;
const button = ymFindReaction(kind);
if (!button) return false;
const before = ymControlOn(button);
ymClick(button);
for (let tick = 0; tick < 8; tick++) {
  await ymSleep(50);
  if (ymControlOn(ymFindReaction(kind)) !== before) return true;
}
return false;
""",
        KIND=kind,
    )


def navigate_script(target: str) -> str:
    return fill(
        r"""
const target = __TARGET__;
const bar = ymById("VIBE_DYNAMIC_ARTISTS") || ymById("PLAYERBAR_DESKTOP");
if (target === "artist") {
  const link = bar && bar.querySelector('[data-test-id="SEPARATED_ARTIST_TITLE"] a, a[href*="artist"]');
  if (!link) return false;
  ymClick(link);
  return true;
}
const box = ymById("VIBE_ALBUM_COVER") || ymById("PLAYERBAR_DESKTOP_COVER_CONTAINER");
const link = box && box.querySelector("a");
if (link) { ymClick(link); return true; }
const button = ymById("ENTITY_COVER_BUTTON");
if (!button) return false;
ymClick(button);
return true;
""",
        TARGET=target,
    )


def track_page_script(track_id: int, album_id: int | None, action: str) -> str:
    """Сразу открывает album/track по id. Текущий документ не используется как источник строки."""
    return fill(
        r"""
const trackId = String(__TRACK_ID__);
const albumId = __ALBUM_ID__ == null ? "" : String(__ALBUM_ID__);
const action = __ACTION__;
function trackPath() {
  const query = albumId
    ? ("albumId=" + encodeURIComponent(albumId) + "&trackId=" + encodeURIComponent(trackId))
    : ("trackId=" + encodeURIComponent(trackId));
  return "/album/track?" + query;
}
let opened = false;
async function openTrack() {
  if (onTrackPage()) return;
  opened = true;
  await ymInAppGo(trackPath());
}
function retreat() {
  if (opened && action !== "play") history.back();
}
function onTrackPage() {
  const href = location.href;
  if (!href.includes("trackId=" + trackId)) return false;
  if (albumId && !href.includes("albumId=" + albumId)) return false;
  return true;
}
function badHost(el) {
  return el.closest('[data-test-id="TRACK_PAGE_SIMILAR_TRACKS"], [data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"], [data-test-id="SEARCH_TRACK"]');
}
function findTrackPlay() {
  const areas = ["TRACK_PAGE_CONTENT", "ENTITY_HEADER", "BASE_PAGE_HEADER_CONTROLS", "BLOCK_HEADER"];
  for (const areaId of areas) {
    const area = ymById(areaId);
    if (!area) continue;
    const withCover = area.querySelector('[data-test-id="PLAY_BUTTON_WITH_COVER"]');
    if (withCover && !badHost(withCover)) {
      const inner = withCover.querySelector('[data-test-id="PLAY_BUTTON"]');
      if (inner && ymVisible(inner, 8)) return inner;
      if (ymVisible(withCover, 8)) return withCover;
    }
    for (const button of area.querySelectorAll('[data-test-id="PLAY_BUTTON"]')) {
      if (!badHost(button) && ymVisible(button, 8)) return button;
    }
    for (const button of area.querySelectorAll("button")) {
      const label = button.getAttribute("aria-label") || "";
      if ((label.includes("Воспроизведение") || label.includes("Слушать")) && !badHost(button) && ymVisible(button, 8)) return button;
    }
  }
  return null;
}
function barHasTrack() {
  const bar = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || document.body;
  const link = bar.querySelector('a[href*="trackId=' + trackId + '"]');
  const pause = bar.querySelector('[data-test-id="PAUSE_BUTTON"]') || bar.querySelector('[aria-label="Пауза"]');
  return !!(link && pause && ymVisible(pause));
}
function outsideTrack(node) {
  if (!node || !node.closest) return true;
  if (node.closest('[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"], [data-test-id="ARTIST_FAMILIAR_PAGE"], [data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE"]')) return true;
  const row = node.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]');
  if (!row) return false;
  const anchor = row.querySelector('a[href*="trackId="], a[href*="/track/"]');
  if (!anchor) return true;
  try {
    const url = new URL(anchor.getAttribute("href") || anchor.href, location.href);
    return url.searchParams.get("trackId") !== trackId;
  } catch (error) { return true; }
}
function menuItem() {
  const page = ymById("TRACK_PAGE");
  if (!page || !onTrackPage()) return null;
  const menus = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]')).filter((menu) => ymVisible(menu) && !outsideTrack(menu));
  const root = menus[0];
  if (!root || outsideTrack(root)) return null;
  if (action === "next") {
    const found = ymById("TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON", root) || ymById("TRACK_CONTEXT_MENU_PLAY_NEXT", root);
    return found && root.contains(found) && !outsideTrack(found) ? found : null;
  }
  const found = ymById("TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", root)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE", root)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE_BUTTON", root)
    || ymById("TRACK_CONTEXT_MENU_QUEUE", root)
    || root.querySelector('[data-test-id*="ADD_TO_QUEUE"]');
  return found && root.contains(found) && !outsideTrack(found) ? found : null;
}
await openTrack();
for (let step = 0; step < 60; step++) {
  await ymSleep(250);
  if ((step === 4 || step === 12) && !onTrackPage()) await openTrack();
  if (!onTrackPage()) continue;
  if (action === "play") {
    if (barHasTrack()) return "playing";
    const button = findTrackPlay();
    if (!button) continue;
    ymClick(button);
    await ymSleep(200);
    if (barHasTrack()) return "started";
    continue;
  }
  const page = ymById("TRACK_PAGE");
  if (!page || !onTrackPage()) continue;
  const menuButton = ymById("TRACK_HEADER_CONTEXT_MENU_BUTTON", page) || ymById("TRACK_CONTEXT_MENU_BUTTON", page);
  if (!menuButton || !page.contains(menuButton) || outsideTrack(menuButton)) continue;
  ymClick(menuButton);
  await ymSleep(520);
  const item = menuItem();
  if (!item) { ymPressEscape(); retreat(); return "no_menu"; }
  ymClick(item);
  await ymSleep(250);
  ymPressEscape();
  retreat();
  return "ok";
}
retreat();
return "fail";
""",
        TRACK_ID=track_id,
        ALBUM_ID=album_id,
        ACTION=action,
    )


def playlist_script(
    playlist_uuid: str,
    track_id: int,
    album_id: int | None,
    index: int | None,
    action: str,
) -> str:
    """Сначала открывает плейлист команды. Индекс только подсказывает прокрутку, строка ищется по числовому trackId."""
    return fill(
        r"""
const playlistUuid = String(__PLAYLIST_UUID__);
const trackId = String(__TRACK_ID__);
const wanted = Number(trackId);
const albumId = __ALBUM_ID__ == null ? "" : String(__ALBUM_ID__);
const index = __INDEX__;
const action = __ACTION__;
const storageKey = "ym:" + trackId + ":" + action;
sessionStorage.removeItem(storageKey);
function playlistPath() {
  return "/playlists?playlistUuid=" + encodeURIComponent(playlistUuid);
}
function onPlaylist() {
  try { return new URL(location.href).searchParams.get("playlistUuid") === playlistUuid; }
  catch (error) { return false; }
}
let opened = false;
function retreat() {
  if (opened && action !== "play") history.back();
}
function queueOpen() {
  const panel = ymById("PLAY_QUEUE");
  if (!panel) return false;
  const rect = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  return rect.width >= 2 && rect.height >= 2 && style.display !== "none" && style.visibility !== "hidden";
}
function queueToggle() {
  const panel = ymById("PLAY_QUEUE");
  const modal = ymById("FULLSCREEN_PLAYER_MODAL");
  const picks = [];
  if (panel && modal && modal.contains(panel)) {
    const full = ymById("FULLSCREEN_PLAYER_QUEUE_BUTTON");
    if (full) picks.push(full);
  }
  for (const el of document.querySelectorAll("button, [role='button']")) {
    const id = el.getAttribute("data-test-id") || "";
    if (id.indexOf("PLAY_QUEUE") === -1 || id === "PLAY_QUEUE") continue;
    picks.push(el);
  }
  const bar = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
  if (bar) picks.push(bar);
  for (const el of picks) {
    if (!ymVisible(el)) continue;
    const rect = el.getBoundingClientRect();
    const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    const covered = panel && top && (top === panel || panel.contains(top)) && !panel.contains(el);
    if (!covered) return el;
  }
  return picks.find((el) => ymVisible(el)) || picks[0] || null;
}
if (queueOpen()) {
  for (let attempt = 0; attempt < 4 && queueOpen(); attempt++) {
    const toggle = queueToggle();
    if (!toggle) break;
    ymClick(toggle);
    await ymSleep(200);
  }
}
const wasHere = onPlaylist();
await ymInAppGo(playlistPath());
opened = !wasHere;
let ready = false;
for (let attempt = 0; attempt < 40; attempt++) {
  if (onPlaylist() && ymById("PLAYLIST_PAGE")) { ready = true; break; }
  if (attempt === 8 || attempt === 18) await ymInAppGo(playlistPath());
  await ymSleep(150);
}
if (!ready) { retreat(); return "fail"; }
function numericId(anchor) {
  if (!anchor) return null;
  let url;
  try { url = new URL(anchor.getAttribute("href") || anchor.href, location.href); }
  catch (error) { return null; }
  const raw = url.searchParams.get("trackId");
  if (raw && /^\d+$/.test(raw)) return Number(raw);
  const parts = url.pathname.split("/");
  const at = parts.lastIndexOf("track");
  if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return Number(parts[at + 1]);
  return null;
}
function albumOf(anchor) {
  if (!anchor) return "";
  let url;
  try { url = new URL(anchor.getAttribute("href") || anchor.href, location.href); }
  catch (error) { return ""; }
  const raw = url.searchParams.get("albumId");
  if (raw && /^\d+$/.test(raw)) return raw;
  const parts = url.pathname.split("/");
  const at = parts.lastIndexOf("album");
  if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return parts[at + 1];
  return "";
}
function forbidden(node) {
  return !!(node && node.closest && node.closest('[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"], [data-test-id="ARTIST_FAMILIAR_PAGE"], [data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE"]'));
}
function rowTrackId(candidate) {
  const page = ymById("PLAYLIST_PAGE");
  if (!candidate || !page || !page.contains(candidate) || forbidden(candidate)) return null;
  for (const anchor of candidate.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    const id = numericId(anchor);
    if (id != null) return id;
  }
  return null;
}
function findRow() {
  const page = ymById("PLAYLIST_PAGE");
  if (!page) return null;
  for (const anchor of page.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    if (forbidden(anchor)) continue;
    if (numericId(anchor) !== wanted) continue;
    const album = albumOf(anchor);
    if (albumId && album && album !== albumId) continue;
    const row = anchor.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]');
    if (row && page.contains(row) && !forbidden(row) && rowTrackId(row) === wanted) return row;
  }
  return null;
}
function playlistTools() {
  const page = ymById("PLAYLIST_PAGE");
  const scroller = page && page.querySelector('[data-test-id="virtuoso-scroller"]');
  try {
  let store = null;
  let api = null;
  if (scroller) {
    const fiberKey = Object.keys(scroller).find((name) => name.indexOf("__reactFiber") === 0 || name.indexOf("__reactInternalInstance") === 0);
    let fiber = fiberKey ? scroller[fiberKey] : null;
    for (let depth = 0; fiber && depth < 80; depth += 1, fiber = fiber.return) {
      const buckets = [fiber.memoizedProps];
      let state = fiber.memoizedState;
      let guard = 0;
      while (state && guard < 40) {
        buckets.push(state.memoizedState);
        state = state.next;
        guard += 1;
      }
      for (const bucket of buckets) {
        if (!bucket || typeof bucket !== "object" || bucket.nodeType) continue;
        const candidates = [bucket].concat(Object.values(bucket).filter((item) => item && typeof item === "object" && !item.nodeType));
        for (const candidate of candidates) {
          if (!store && typeof candidate.getTracksByRange === "function" && Array.isArray(candidate.items)) store = candidate;
        }
        if (bucket.totalListHeight && bucket.totalCount) api = bucket;
      }
    }
  }
  return { scroller, store, api };
  } catch (error) {
    return { scroller, store: null, api: null };
  }
}
function rowHeight() {
  const sample = document.querySelector('[data-test-id="PLAYLIST_PAGE"] [data-test-id="TRACK_PLAYLIST"]');
  const height = sample ? sample.getBoundingClientRect().height : 56;
  return height > 20 ? height : 56;
}
function visibleIndexes() {
  return Array.from(document.querySelectorAll('[data-test-id="PLAYLIST_PAGE"] [data-index]')).map((node) => Number(node.getAttribute("data-index"))).filter((value) => Number.isFinite(value));
}
function indexInStore(store) {
  if (!store || !Array.isArray(store.items)) return null;
  for (let i = 0; i < store.items.length; i++) {
    const item = store.items[i];
    if (!item) continue;
    const candidates = [item.id, item.trackId, item.key, item.data && item.data.id, item.data && item.data.realId];
    for (const candidate of candidates) {
      if (candidate == null) continue;
      const head = String(candidate).split(":")[0];
      if (Number(head) === wanted) return i;
    }
  }
  return null;
}
let row = null;
let endHits = 0;
let hinted = false;
let landedMiss = 0;
for (let step = 0; step < 36; step++) {
  sessionStorage.setItem(storageKey, String(step));
  row = findRow();
  if (row) break;
  const tools = playlistTools();
  const scroller = tools.scroller;
  if (!scroller) { await ymSleep(180); continue; }
  const height = rowHeight();
  const count = tools.store && Array.isArray(tools.store.items) ? tools.store.items.length : 0;
  const stored = indexInStore(tools.store);
  const focus = stored != null ? stored : (index == null ? 0 : index);
  try {
    if (tools.store) tools.store.getTracksByRange({ startIndex: Math.max(0, focus - 8), endIndex: focus + 12 });
  } catch (error) {}
  if (tools.api && count > 0 && typeof tools.api.totalListHeight === "function") {
    const known = Number(tools.api.totalListHeight(4)) || 0;
    if (known < count * height * 0.5) {
      tools.api.totalListHeight(0, count * height);
      const nudge = scroller.scrollTop;
      scroller.scrollTop = nudge + 1;
      scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
      await ymSleep(180);
    }
  }
  const hintTop = stored == null && index == null ? 0 : Math.max(0, (focus - 2) * height);
  const neededTop = hintTop + scroller.clientHeight + height;
  if (focus != null && scroller.scrollHeight < neededTop && tools.api && typeof tools.api.totalListHeight === "function") {
    const slots = Math.max(count, focus + 8);
    tools.api.totalListHeight(0, slots * height);
    scroller.scrollTop = 1;
    scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
    await ymSleep(200);
  }
  const visible = visibleIndexes();
  let targetTop = stored == null && index == null ? (hinted ? scroller.scrollTop + Math.max(height * 8, scroller.clientHeight * 0.72) : 0) : hintTop;
  if (visible.length && hinted && (stored != null || index != null)) {
    const min = Math.min.apply(null, visible);
    const max = Math.max.apply(null, visible);
    const delta = Math.max(height * 8, scroller.clientHeight * 0.72);
    if (max < focus - 2) targetTop = Math.max(hintTop, scroller.scrollTop + delta);
    else if (min > focus + 2) targetTop = Math.min(hintTop, Math.max(0, scroller.scrollTop - delta));
  }
  const before = scroller.scrollTop;
  scroller.scrollTop = targetTop;
  scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
  hinted = true;
  const landed = (stored == null && index == null) || Math.abs(scroller.scrollTop - hintTop) < height * 4 || (visible.length && Math.max.apply(null, visible) >= focus - 2);
  if (landed) {
    for (let wait = 0; wait < 8; wait++) {
      await ymSleep(200);
      row = findRow();
      if (row) break;
      try {
        if (tools.store) tools.store.getTracksByRange({ startIndex: Math.max(0, focus - 8), endIndex: focus + 12 });
      } catch (error) {}
    }
    if (row) break;
  }
  const atEnd = landed && Math.abs(scroller.scrollTop - before) < 1 && scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 4;
  if (atEnd) {
    endHits += 1;
    if (endHits >= 8) { retreat(); return "fail"; }
  } else endHits = 0;
  if (landed && !row) {
    landedMiss += 1;
    if (landedMiss >= 6) { retreat(); return "fail"; }
  } else landedMiss = 0;
  if (!landed) await ymSleep(160);
}
async function revealAgain() {
  for (let pass = 0; pass < 4; pass++) {
    row = findRow();
    if (rowTrackId(row) === wanted) return row;
    const tools = playlistTools();
    const scroller = tools.scroller;
    if (!scroller) { await ymSleep(160); continue; }
    const stored = indexInStore(tools.store);
    const focus = stored != null ? stored : (index == null ? 0 : index);
    const height = rowHeight();
    try {
      if (tools.store) tools.store.getTracksByRange({ startIndex: Math.max(0, focus - 8), endIndex: focus + 12 });
    } catch (error) {}
    if (tools.api && typeof tools.api.totalListHeight === "function") {
      const count = tools.store && Array.isArray(tools.store.items) ? tools.store.items.length : 0;
      const slots = Math.max(count, focus + 8);
      if (scroller.scrollHeight < (focus + 2) * height) tools.api.totalListHeight(0, slots * height);
    }
    scroller.scrollTop = Math.max(0, (focus - 2) * height);
    scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
    await ymSleep(280);
  }
  row = findRow();
  return rowTrackId(row) === wanted ? row : null;
}
if (!row || rowTrackId(row) !== wanted) row = await revealAgain();
if (!row || rowTrackId(row) !== wanted) { retreat(); return "fail"; }
if (row.scrollIntoView) row.scrollIntoView({ block: "center" });
await ymSleep(140);
if (rowTrackId(row) !== wanted) {
  row = await revealAgain();
  if (!row) { retreat(); return "fail"; }
}
if (action === "play") {
  let button = null;
  for (const candidate of row.querySelectorAll('[data-test-id="PLAY_BUTTON"], button')) {
    if (!ymVisible(candidate)) continue;
    const id = candidate.getAttribute("data-test-id") || "";
    const label = candidate.getAttribute("aria-label") || "";
    if (id === "PLAY_BUTTON" || label.includes("Слушать") || label.includes("Воспроизведение")) { button = candidate; break; }
  }
  if (!button || forbidden(button) || !row.contains(button) || rowTrackId(row) !== wanted) return "fail";
  ymClick(button);
  for (let check = 0; check < 6; check++) {
    await ymSleep(120);
    const bar = ymById("PLAYERBAR_DESKTOP") || document;
    const link = bar.querySelector('a[href*="trackId=' + trackId + '"]');
    const pause = bar.querySelector('[data-test-id="PAUSE_BUTTON"]') || bar.querySelector('[aria-label="Пауза"]');
    if (link && pause && ymVisible(pause)) return "playing";
  }
  retreat();
  return "fail";
}
let seenMenus = new Set();
function nearestMenu(menus) {
  const box = row.getBoundingClientRect();
  const ax = box.left + box.width / 2;
  const ay = box.top + box.height / 2;
  let best = null;
  let bestDist = Infinity;
  for (const menu of menus) {
    if (forbidden(menu) || !ymVisible(menu)) continue;
    const rect = menu.getBoundingClientRect();
    const dx = (rect.left + rect.width / 2) - ax;
    const dy = (rect.top + rect.height / 2) - ay;
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) { bestDist = dist; best = menu; }
  }
  return best;
}
function menuForRow() {
  if (rowTrackId(row) !== wanted) return null;
  const all = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]')).filter((menu) => !forbidden(menu));
  const fresh = all.filter((menu) => !seenMenus.has(menu) && ymVisible(menu));
  if (fresh.length) return nearestMenu(fresh);
  const button = row.querySelector('[data-test-id="TRACK_CONTEXT_MENU_BUTTON"][aria-expanded="true"], [data-test-id="TRACK_PLAYLIST_CONTEXT_MENU_BUTTON"][aria-expanded="true"]');
  if (!button || !row.contains(button) || forbidden(button)) return null;
  const eligible = all.filter((menu) => ymVisible(menu));
  return eligible.length ? nearestMenu(eligible) : null;
}
function menuItem() {
  const menu = menuForRow();
  if (!menu || forbidden(menu) || rowTrackId(row) !== wanted) return null;
  if (action === "next") {
    const found = ymById("TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON", menu) || ymById("TRACK_CONTEXT_MENU_PLAY_NEXT", menu);
    return found && menu.contains(found) && !forbidden(found) ? found : null;
  }
  const found = ymById("TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_QUEUE", menu)
    || menu.querySelector('[data-test-id*="ADD_TO_QUEUE"]');
  return found && menu.contains(found) && !forbidden(found) ? found : null;
}
function openRowMenu() {
  if (rowTrackId(row) !== wanted) return false;
  row.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
  row.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  let menuButton = null;
  for (const id of ["TRACK_CONTEXT_MENU_BUTTON", "TRACK_PLAYLIST_CONTEXT_MENU_BUTTON", "CONTEXT_MENU_BUTTON"]) {
    const found = ymById(id, row);
    if (found && row.contains(found) && !forbidden(found)) { menuButton = found; break; }
  }
  if (!menuButton) {
    for (const candidate of row.querySelectorAll("button")) {
      if (!row.contains(candidate) || forbidden(candidate)) continue;
      const label = (candidate.getAttribute("aria-label") || "").toLowerCase();
      if (label.includes("ещё") || label.includes("опци") || label.includes("меню") || label.includes("контекст")) { menuButton = candidate; break; }
    }
  }
  if (!menuButton) return false;
  seenMenus = new Set(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]'));
  ymClick(menuButton);
  return true;
}
let item = null;
for (let attempt = 0; attempt < 4 && !item; attempt++) {
  if (rowTrackId(row) !== wanted) {
    ymPressEscape();
    row = await revealAgain();
    if (!row) break;
  }
  ymPressEscape();
  await ymSleep(80);
  if (!openRowMenu()) { ymPressEscape(); row = await revealAgain(); continue; }
  await ymSleep(480);
  if (rowTrackId(row) !== wanted) { ymPressEscape(); row = null; continue; }
  item = menuItem();
  if (!item || forbidden(item)) { item = null; ymPressEscape(); }
}
if (!item || rowTrackId(row) !== wanted || forbidden(item)) { ymPressEscape(); retreat(); return "no_menu"; }
const openedMenu = item.closest('[data-test-id="TRACK_CONTEXT_MENU"]');
const menuAnchor = openedMenu && openedMenu.querySelector('a[href*="trackId="], a[href*="/track/"]');
const menuTrack = menuAnchor ? numericId(menuAnchor) : null;
if (menuTrack != null && menuTrack !== wanted) { ymPressEscape(); retreat(); return "no_menu"; }
if (forbidden(item) || (openedMenu && forbidden(openedMenu))) { ymPressEscape(); retreat(); return "no_menu"; }
ymClick(item);
await ymSleep(250);
ymPressEscape();
retreat();
return "ok";
""",
        PLAYLIST_UUID=playlist_uuid,
        TRACK_ID=track_id,
        ALBUM_ID=album_id,
        INDEX=index,
        ACTION=action,
    )


def search_script(query: str) -> str:
    return fill(
        r"""
const query = __QUERY__;
function titlesOf(cards) {
  return Array.from(cards).slice(0, 8).map((card) => ymText(ymById("TRACK_TITLE", card))).join("|");
}
const queuePanel = ymById("PLAY_QUEUE");
const queueButton = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
if (queuePanel && ymVisible(queuePanel) && queueButton) {
  ymClick(queueButton);
  await ymSleep(250);
}
const before = titlesOf(document.querySelectorAll('[data-test-id="SEARCH_TRACK_CARD"]'));
const nav = ymById("NAVBAR_NAVIGATION_ITEM_SEARCH");
if (!nav) return { ok: false, code: "no_button" };
ymClick(nav);
await ymSleep(700);
let page = null;
for (let attempt = 0; attempt < 15; attempt++) {
  page = ymById("SEARCH_PAGE");
  if (page) break;
  await ymSleep(150);
}
if (!page) return { ok: false, code: "no_page" };
function findInput() {
  return (ymById("SEARCH_PAGE_SEARCH_INPUT") && (ymById("SEARCH_PAGE_SEARCH_INPUT").querySelector("input") || ymById("SEARCH_PAGE_SEARCH_INPUT")))
    || (ymById("SEARCH_INPUT") && (ymById("SEARCH_INPUT").querySelector("input") || ymById("SEARCH_INPUT")))
    || document.querySelector('input[placeholder*="чувствуете"], input[placeholder*="оиск"]');
}
const input = findInput();
if (!input || !ymSetNativeValue(input, query)) return { ok: false, code: "no_input" };
const field = input.matches && input.matches("input,textarea") ? input : input.querySelector("input,textarea");
if (field) {
  field.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
  field.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", code: "Enter", bubbles: true }));
}
let cards = [];
for (let attempt = 0; attempt < 25; attempt++) {
  await ymSleep(300);
  cards = Array.from(document.querySelectorAll('[data-test-id="SEARCH_TRACK_CARD"]'));
  const signature = titlesOf(cards);
  if (cards.length && signature && signature !== before) break;
}
const tracks = [];
for (const card of cards) {
  if (tracks.length >= 15) break;
  const title = ymText(ymById("TRACK_TITLE", card));
  const anchor = card.querySelector('a[href*="trackId="], a[href*="/track/"]');
  let trackId = null;
  let albumId = null;
  if (anchor) {
    try {
      const url = new URL(anchor.getAttribute("href") || anchor.href, location.href);
      const rawTrack = url.searchParams.get("trackId");
      const rawAlbum = url.searchParams.get("albumId");
      if (rawTrack && /^\d+$/.test(rawTrack)) trackId = Number(rawTrack);
      if (rawAlbum && /^\d+$/.test(rawAlbum)) albumId = Number(rawAlbum);
      const parts = url.pathname.split("/");
      const albumAt = parts.indexOf("album");
      const trackAt = parts.indexOf("track");
      if (albumId == null && albumAt >= 0 && /^\d+$/.test(parts[albumAt + 1] || "")) albumId = Number(parts[albumAt + 1]);
      if (trackId == null && trackAt >= 0 && /^\d+$/.test(parts[trackAt + 1] || "")) trackId = Number(parts[trackAt + 1]);
    } catch (error) {}
  }
  if (!title || trackId == null) continue;
  let artists = Array.from(card.querySelectorAll('[data-test-id="SEPARATED_ARTIST_TITLE"], .artist, a[href*="/artist"]')).map((el) => ymText(el)).filter(Boolean);
  if (!artists.length) {
    const label = card.getAttribute("aria-label") || "";
    if (label) artists = [label];
  }
  const artistRefs = ymReadArtistRefs(card);
  const image = card.querySelector('[data-test-id="ENTITY_COVER_IMAGE"] img') || card.querySelector('[data-test-id="ENTITY_COVER_IMAGE"]');
  const cover = image ? (image.getAttribute("src") || "") : "";
  tracks.push({ title, artists, artist_refs: artistRefs, track_id: trackId, album_id: albumId, cover });
}
const artistCards = [];
const seenArtists = new Set();
const searchScope = ymById("SEARCH_PAGE") || document;
for (const anchor of searchScope.querySelectorAll('a[href*="artist"]')) {
  if (artistCards.length >= 6) break;
  if (anchor.closest('[data-test-id="SEARCH_TRACK_CARD"], [data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"], [data-test-id="SEPARATED_ARTIST_TITLE"], [data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"]')) continue;
  const artistId = ymArtistIdFromHref(anchor.getAttribute("href") || anchor.href);
  if (artistId == null || seenArtists.has(artistId)) continue;
  const cardRoot = anchor.closest('[data-test-id*="ARTIST"], [data-test-id*="CARD"], li, article') || anchor.parentElement || anchor;
  const titleNode = (cardRoot && (ymById("ARTIST_TITLE", cardRoot) || ymById("TITLE", cardRoot))) || anchor;
  const name = (ymText(anchor) || ymText(titleNode) || (anchor.getAttribute("aria-label") || "")).trim();
  if (!name || name.length > 120) continue;
  seenArtists.add(artistId);
  const img = cardRoot ? (cardRoot.querySelector('[data-test-id="ENTITY_COVER_IMAGE"] img') || cardRoot.querySelector("img")) : null;
  const cover = img ? (img.getAttribute("src") || "") : "";
  artistCards.push({ id: artistId, name, cover });
}
function ownLine(node, testId) {
  const el = ymById(testId, node);
  return el ? ymText(el).replace(/\s+/g, " ").trim() : "";
}
const waves = [];
let lumen = null;
const lumenNode = ymById("QUERY_TO_VIBE_BLOCK", searchScope);
if (lumenNode) {
  const title = ownLine(lumenNode, "ENTITY_CARD_ENTITY_META_TITLE");
  const subtitle = ownLine(lumenNode, "ENTITY_CARD_ENTITY_META_DESCRIPTION");
  if (title && title.toLowerCase() !== "моя волна") {
    const art = ymCardArt(lumenNode.parentElement || lumenNode);
    lumen = { title, subtitle, cover: art.cover || "", background: art.background || "" };
  }
}
for (const node of searchScope.querySelectorAll('[data-test-id="SEARCH_VIBE_CARD"]')) {
  if (waves.length >= 20) break;
  if (lumenNode && lumenNode.contains(node)) continue;
  const title = ownLine(node, "ENTITY_CARD_ENTITY_META_TITLE");
  const subtitle = ownLine(node, "ENTITY_CARD_ENTITY_META_DESCRIPTION");
  if (!title || title.toLowerCase() === "моя волна") continue;
  if ((subtitle || "").toLowerCase().includes("люмен")) continue;
  const art = ymCardArt(node);
  waves.push({ title, subtitle, cover: art.cover || "", background: art.background || "" });
}
return { ok: true, tracks, artist_cards: artistCards, waves, lumen };
""",
        QUERY=query,
    )


def queue_script(mode: str = "read") -> str:
    return fill(
        r"""
const mode = __MODE__;
async function ensureQueue(waitMs) {
  const panel = ymById("PLAY_QUEUE");
  const rect = panel ? panel.getBoundingClientRect() : null;
  if (!panel || !rect || rect.width < 2 || rect.height < 2) {
    const button = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
    if (!button) return false;
    ymClick(button);
    await ymSleep(waitMs);
  }
  const opened = ymById("PLAY_QUEUE");
  if (!opened) return false;
  const box = opened.getBoundingClientRect();
  return box.width >= 2 && box.height >= 2;
}
function parseRow(row) {
  const anchor = row.querySelector('a[href*="trackId="]');
  let parsedTrack = null;
  let parsedAlbum = null;
  if (anchor) {
    try {
      const url = new URL(anchor.href, location.href);
      const rawTrack = url.searchParams.get("trackId");
      const rawAlbum = url.searchParams.get("albumId");
      if (rawTrack && /^\d+$/.test(rawTrack)) parsedTrack = Number(rawTrack);
      if (rawAlbum && /^\d+$/.test(rawAlbum)) parsedAlbum = Number(rawAlbum);
    } catch (error) {}
  }
  const artists = Array.from(row.querySelectorAll('[data-test-id="SEPARATED_ARTIST_TITLE"]')).map((el) => ymText(el)).filter(Boolean);
  const artistRefs = ymReadArtistRefs(row);
  const image = row.querySelector('[data-test-id="ENTITY_COVER_IMAGE"] img') || row.querySelector('[data-test-id="ENTITY_COVER_IMAGE"]');
  return {
    title: ymText(ymById("TRACK_TITLE", row)),
    artists,
    artist_refs: artistRefs,
    cover: image ? (image.getAttribute("src") || "") : "",
    track_id: parsedTrack,
    album_id: parsedAlbum,
    is_playing: !!row.querySelector('[data-test-id="PAUSE_BUTTON"]')
  };
}
function parseBlock(id) {
  const block = ymById(id);
  if (!block) return [];
  return Array.from(block.querySelectorAll('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]')).map(parseRow);
}
function readQueue() {
  const now = parseBlock("PLAY_QUEUE_NOW_PLAYING_BLOCK");
  const afterTitle = ymText(ymById("PLAY_QUEUE_AFTER_PLAYING_BLOCK_TITLE")) || "Далее в очереди";
  return {
    ok: true,
    before: parseBlock("PLAY_QUEUE_BEFORE_PLAYING_BLOCK"),
    current: now.length ? now[0] : null,
    after: parseBlock("PLAY_QUEUE_AFTER_PLAYING_BLOCK"),
    after_title: afterTitle,
    now_meta: {
      subtitle: ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_SUBTITLE")),
      source: ymText(ymById("PLAY_QUEUE_NOW_PLAYING_BLOCK_TITLE"))
    }
  };
}
const empty = { ok: true, before: [], current: null, after: [], after_title: "Далее в очереди", now_meta: { subtitle: "", source: "" } };
if (mode !== "read" || !(await ensureQueue(350))) return empty;
return readQueue();
""",
        MODE=mode,
    )


def artist_play_script(artist_id: int) -> str:
    return fill(
        r"""
const artistId = String(__ARTIST_ID__);
function primaryPath() {
  return "/artist?artistId=" + encodeURIComponent(artistId);
}
function altPath() {
  return "/artist/" + encodeURIComponent(artistId);
}
function onArtist() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("artistId") === artistId) {
      return !url.pathname.includes("/tracks") && !url.pathname.includes("/familiar");
    }
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("artist");
    return at >= 0 && parts[at + 1] === artistId && parts.length === at + 2;
  } catch (error) { return false; }
}
function queueOpen() {
  const panel = ymById("PLAY_QUEUE");
  if (!panel) return false;
  const rect = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  return rect.width >= 2 && rect.height >= 2 && style.display !== "none" && style.visibility !== "hidden";
}
function queueToggle() {
  const panel = ymById("PLAY_QUEUE");
  const modal = ymById("FULLSCREEN_PLAYER_MODAL");
  const picks = [];
  if (panel && modal && modal.contains(panel)) {
    const full = ymById("FULLSCREEN_PLAYER_QUEUE_BUTTON");
    if (full) picks.push(full);
  }
  for (const el of document.querySelectorAll("button, [role='button']")) {
    const id = el.getAttribute("data-test-id") || "";
    if (id.indexOf("PLAY_QUEUE") === -1 || id === "PLAY_QUEUE") continue;
    picks.push(el);
  }
  const bar = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
  if (bar) picks.push(bar);
  return picks.find((el) => ymVisible(el)) || picks[0] || null;
}
if (queueOpen()) {
  for (let attempt = 0; attempt < 4 && queueOpen(); attempt++) {
    const toggle = queueToggle();
    if (!toggle) break;
    ymClick(toggle);
    await ymSleep(200);
  }
}
if (!onArtist()) await ymInAppGo(primaryPath());
function badHost(el) {
  if (!el || !el.closest) return true;
  if (el.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"], [data-test-id="SEARCH_TRACK"], [data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"], [data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE"]')) return true;
  if (el.closest('a[href*="albumId="], a[href*="/album/"]')) return true;
  const id = (el.getAttribute("data-test-id") || "").toUpperCase();
  const label = (el.getAttribute("aria-label") || "").toLowerCase();
  const text = ymText(el).toLowerCase();
  if (id.includes("TRAILER") || label.includes("трейлер") || text.includes("трейлер")) return true;
  return false;
}
function headerScopes() {
  const scopes = [];
  for (const id of ["ENTITY_HEADER", "BASE_PAGE_HEADER_CONTROLS", "ARTIST_HEADER", "ARTIST_PAGE", "BLOCK_HEADER"]) {
    const el = ymById(id);
    if (el) scopes.push(el);
  }
  return scopes;
}
function headerAlreadyPlaying() {
  for (const area of headerScopes()) {
    for (const pause of area.querySelectorAll('[data-test-id="PAUSE_BUTTON"]')) {
      if (!badHost(pause) && ymVisible(pause, 8) && ymTransportPlaying()) return true;
    }
  }
  return false;
}
function findHeaderPlay() {
  for (const area of headerScopes()) {
    const withCover = area.querySelector('[data-test-id="PLAY_BUTTON_WITH_COVER"]');
    if (withCover && !badHost(withCover)) {
      const inner = withCover.querySelector('[data-test-id="PLAY_BUTTON"]');
      if (inner && !badHost(inner) && ymVisible(inner, 8)) return inner;
      if (ymVisible(withCover, 8)) return withCover;
    }
    for (const button of area.querySelectorAll('[data-test-id="PLAY_BUTTON"]')) {
      if (!badHost(button) && ymVisible(button, 8)) return button;
    }
    for (const button of area.querySelectorAll("button")) {
      const label = button.getAttribute("aria-label") || "";
      if ((label.includes("Слушать") || label.includes("Воспроизведение")) && !badHost(button) && ymVisible(button, 8)) return button;
    }
  }
  return null;
}
for (let step = 0; step < 50; step++) {
  await ymSleep(200);
  if (step === 8 && !onArtist()) {
    const nextPath = location.protocol === "music-application:" ? primaryPath() : altPath();
    await ymInAppGo(nextPath);
  }
  if (step === 18 && !onArtist()) await ymInAppGo(primaryPath());
  if (!onArtist()) continue;
  if (headerAlreadyPlaying()) return "playing";
  const button = findHeaderPlay();
  if (!button) continue;
  ymClick(button);
  for (let check = 0; check < 10; check++) {
    await ymSleep(150);
    if (ymTransportPlaying()) return "playing";
  }
}
return "fail";
""",
        ARTIST_ID=artist_id,
    )


def album_play_script(album_id: int) -> str:
    return fill(
        r"""
const albumId = String(__ALBUM_ID__);
function primaryPath() {
  return "/album?albumId=" + encodeURIComponent(albumId);
}
function altPath() {
  return "/album/" + encodeURIComponent(albumId);
}
function onAlbum() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("trackId")) return false;
    if (url.searchParams.get("albumId") === albumId) return true;
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("album");
    return at >= 0 && parts[at + 1] === albumId && !parts.includes("track");
  } catch (error) { return false; }
}
function queueOpen() {
  const panel = ymById("PLAY_QUEUE");
  if (!panel) return false;
  const rect = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  return rect.width >= 2 && rect.height >= 2 && style.display !== "none" && style.visibility !== "hidden";
}
function queueToggle() {
  const panel = ymById("PLAY_QUEUE");
  const modal = ymById("FULLSCREEN_PLAYER_MODAL");
  const picks = [];
  if (panel && modal && modal.contains(panel)) {
    const full = ymById("FULLSCREEN_PLAYER_QUEUE_BUTTON");
    if (full) picks.push(full);
  }
  for (const el of document.querySelectorAll("button, [role='button']")) {
    const id = el.getAttribute("data-test-id") || "";
    if (id.indexOf("PLAY_QUEUE") === -1 || id === "PLAY_QUEUE") continue;
    picks.push(el);
  }
  const bar = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
  if (bar) picks.push(bar);
  return picks.find((el) => ymVisible(el)) || picks[0] || null;
}
if (queueOpen()) {
  for (let attempt = 0; attempt < 4 && queueOpen(); attempt++) {
    const toggle = queueToggle();
    if (!toggle) break;
    ymClick(toggle);
    await ymSleep(200);
  }
}
if (!onAlbum()) await ymInAppGo(primaryPath());
function badHost(el) {
  if (!el || !el.closest) return true;
  if (el.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"], [data-test-id="SEARCH_TRACK"], [data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"]')) return true;
  const id = (el.getAttribute("data-test-id") || "").toUpperCase();
  const label = (el.getAttribute("aria-label") || "").toLowerCase();
  const text = ymText(el).toLowerCase();
  if (id.includes("TRAILER") || label.includes("трейлер") || text.includes("трейлер")) return true;
  return false;
}
function headerScopes() {
  const scopes = [];
  for (const id of ["ENTITY_HEADER", "BASE_PAGE_HEADER_CONTROLS", "ALBUM_PAGE", "BLOCK_HEADER"]) {
    const el = ymById(id);
    if (el) scopes.push(el);
  }
  return scopes;
}
function headerAlreadyPlaying() {
  for (const area of headerScopes()) {
    for (const pause of area.querySelectorAll('[data-test-id="PAUSE_BUTTON"]')) {
      if (!badHost(pause) && ymVisible(pause, 8) && ymTransportPlaying()) return true;
    }
  }
  return false;
}
function findHeaderPlay() {
  for (const area of headerScopes()) {
    const withCover = area.querySelector('[data-test-id="PLAY_BUTTON_WITH_COVER"]');
    if (withCover && !badHost(withCover)) {
      const inner = withCover.querySelector('[data-test-id="PLAY_BUTTON"]');
      if (inner && !badHost(inner) && ymVisible(inner, 8)) return inner;
      if (ymVisible(withCover, 8)) return withCover;
    }
    for (const button of area.querySelectorAll('[data-test-id="PLAY_BUTTON"]')) {
      if (!badHost(button) && ymVisible(button, 8)) return button;
    }
    for (const button of area.querySelectorAll("button")) {
      const label = button.getAttribute("aria-label") || "";
      if ((label.includes("Слушать") || label.includes("Воспроизведение")) && !badHost(button) && ymVisible(button, 8)) return button;
    }
  }
  return null;
}
for (let step = 0; step < 50; step++) {
  await ymSleep(200);
  if (step === 8 && !onAlbum()) {
    const nextPath = location.protocol === "music-application:" ? primaryPath() : altPath();
    await ymInAppGo(nextPath);
  }
  if (step === 18 && !onAlbum()) await ymInAppGo(primaryPath());
  if (!onAlbum()) continue;
  if (headerAlreadyPlaying()) return "playing";
  const button = findHeaderPlay();
  if (!button) continue;
  ymClick(button);
  for (let check = 0; check < 10; check++) {
    await ymSleep(150);
    if (ymTransportPlaying()) return "playing";
  }
}
return "fail";
""",
        ALBUM_ID=album_id,
    )


def artist_row_script(
    artist_id: int,
    mode: str | None,
    track_id: int,
    album_id: int | None,
    index: int | None,
    action: str,
) -> str:
    return fill(
        r"""
const artistId = String(__ARTIST_ID__);
const mode = __MODE__ || "popular";
const isFamiliar = mode === "familiar" || mode === "familiar_collection" || mode === "familiar_wave";
const trackId = String(__TRACK_ID__);
const wanted = Number(trackId);
const albumId = __ALBUM_ID__ == null ? "" : String(__ALBUM_ID__);
const index = __INDEX__;
const action = __ACTION__;
function targetPath() {
  if (mode === "tracks") return "/artist/tracks?artistId=" + encodeURIComponent(artistId);
  if (mode === "familiar_collection") return "/artist/familiar?artistId=" + encodeURIComponent(artistId) + "&tab=collection";
  if (mode === "familiar_wave") return "/artist/familiar?artistId=" + encodeURIComponent(artistId) + "&tab=vibe";
  if (mode === "familiar") return "/artist/familiar?artistId=" + encodeURIComponent(artistId);
  return "/artist?artistId=" + encodeURIComponent(artistId);
}
function onContext() {
  try {
    const url = new URL(location.href);
    const matchesId = url.searchParams.get("artistId") === artistId || url.pathname.split("/").includes(artistId);
    if (!matchesId) return false;
    if (mode === "tracks") return url.pathname.includes("/tracks");
    if (mode === "familiar_wave") return url.pathname.includes("/familiar") && url.searchParams.get("tab") === "vibe";
    if (mode === "familiar_collection") return url.pathname.includes("/familiar") && url.searchParams.get("tab") !== "vibe";
    if (mode === "familiar") return url.pathname.includes("/familiar");
    return !url.pathname.includes("/tracks") && !url.pathname.includes("/familiar");
  } catch (error) { return false; }
}
function pageRoot() {
  if (mode === "tracks") return ymById("ARTIST_TRACKS_PAGE") || ymById("ARTIST_PAGE") || document.querySelector("main");
  if (mode === "familiar_wave") return ymById("FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE") || ymById("ARTIST_FAMILIAR_PAGE") || ymById("ARTIST_PAGE") || document.querySelector("main");
  if (mode === "familiar_collection") return ymById("FAMILIAR_YOU_SCROLLABLE_CONTENT_COLLECTION") || ymById("ARTIST_FAMILIAR_PAGE") || ymById("ARTIST_PAGE") || document.querySelector("main");
  if (mode === "familiar") return ymById("ARTIST_FAMILIAR_PAGE") || ymById("ARTIST_PAGE") || document.querySelector("main");
  return ymById("ARTIST_PAGE") || document.querySelector("main");
}
let opened = false;
function retreat() {
  if (opened && action !== "play") history.back();
}
function queueOpen() {
  const panel = ymById("PLAY_QUEUE");
  if (!panel) return false;
  const rect = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  return rect.width >= 2 && rect.height >= 2 && style.display !== "none" && style.visibility !== "hidden";
}
function queueToggle() {
  const panel = ymById("PLAY_QUEUE");
  const modal = ymById("FULLSCREEN_PLAYER_MODAL");
  const picks = [];
  if (panel && modal && modal.contains(panel)) {
    const full = ymById("FULLSCREEN_PLAYER_QUEUE_BUTTON");
    if (full) picks.push(full);
  }
  for (const el of document.querySelectorAll("button, [role='button']")) {
    const id = el.getAttribute("data-test-id") || "";
    if (id.indexOf("PLAY_QUEUE") === -1 || id === "PLAY_QUEUE") continue;
    picks.push(el);
  }
  const bar = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
  if (bar) picks.push(bar);
  return picks.find((el) => ymVisible(el)) || picks[0] || null;
}
if (queueOpen()) {
  for (let attempt = 0; attempt < 4 && queueOpen(); attempt++) {
    const toggle = queueToggle();
    if (!toggle) break;
    ymClick(toggle);
    await ymSleep(200);
  }
}
const wasHere = onContext();
await ymInAppGo(targetPath());
opened = !wasHere;
let ready = false;
for (let attempt = 0; attempt < 36; attempt++) {
  if (onContext() && pageRoot()) { ready = true; break; }
  if (attempt === 8 || attempt === 18) await ymInAppGo(targetPath());
  await ymSleep(150);
}
if (!ready) { retreat(); return "fail"; }
function numericId(anchor) {
  if (!anchor) return null;
  let url;
  try { url = new URL(anchor.getAttribute("href") || anchor.href, location.href); }
  catch (error) { return null; }
  const raw = url.searchParams.get("trackId");
  if (raw && /^\d+$/.test(raw)) return Number(raw);
  const parts = url.pathname.split("/");
  const at = parts.lastIndexOf("track");
  if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return Number(parts[at + 1]);
  return null;
}
function albumOf(anchor) {
  if (!anchor) return "";
  let url;
  try { url = new URL(anchor.getAttribute("href") || anchor.href, location.href); }
  catch (error) { return ""; }
  const raw = url.searchParams.get("albumId");
  if (raw && /^\d+$/.test(raw)) return raw;
  const parts = url.pathname.split("/");
  const at = parts.lastIndexOf("album");
  if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return parts[at + 1];
  return "";
}
function forbidden(node) {
  if (!node || !node.closest) return true;
  if (node.closest('[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"]')) return true;
  if (!isFamiliar && node.closest('[data-test-id="ARTIST_FAMILIAR_PAGE"], [data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE"], [data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_COLLECTION"]')) return true;
  if (isFamiliar && node.closest('[data-test-id="FAMILIAR_YOU_SECTION_ALBUM"]')) return true;
  if (mode === "familiar_collection" && node.closest('[data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_VIBE"]')) return true;
  if (mode === "familiar_wave" && node.closest('[data-test-id="FAMILIAR_YOU_SCROLLABLE_CONTENT_COLLECTION"]')) return true;
  return false;
}
function rowTrackId(candidate) {
  const page = pageRoot();
  if (!candidate || !page || !page.contains(candidate) || forbidden(candidate)) return null;
  for (const anchor of candidate.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    const id = numericId(anchor);
    if (id != null) return id;
  }
  return null;
}
function findRow() {
  const page = pageRoot();
  if (!page) return null;
  let fallbackRow = null;
  for (const anchor of page.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    if (forbidden(anchor)) continue;
    if (numericId(anchor) !== wanted) continue;
    const row = anchor.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]');
    if (!row || !page.contains(row) || forbidden(row) || rowTrackId(row) !== wanted) continue;
    const album = albumOf(anchor);
    if (!albumId || !album || album === albumId) return row;
    if (!fallbackRow) fallbackRow = row;
  }
  return fallbackRow;
}
function findScroller() {
  const page = pageRoot();
  if (!page) return null;
  const virtuoso = page.querySelector('[data-test-id="virtuoso-scroller"]');
  if (virtuoso) return virtuoso;
  const sample = page.querySelector('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]');
  let cur = sample ? sample.parentElement : page;
  while (cur && cur !== document.body) {
    const style = getComputedStyle(cur);
    const oy = style.overflowY;
    if ((oy === "auto" || oy === "scroll" || oy === "overlay") && cur.scrollHeight > cur.clientHeight + 4) return cur;
    cur = cur.parentElement;
  }
  return null;
}
let row = null;
let hinted = false;
for (let step = 0; step < 30; step++) {
  row = findRow();
  if (row) break;
  const scroller = findScroller();
  if (!scroller) { await ymSleep(180); continue; }
  const sample = document.querySelector('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]');
  const height = sample && sample.getBoundingClientRect().height > 20 ? sample.getBoundingClientRect().height : 56;
  if (!hinted && index != null && index > 0) {
    scroller.scrollTop = Math.max(0, (index - 2) * height);
    hinted = true;
  } else {
    scroller.scrollTop = scroller.scrollTop + Math.max(height * 8, scroller.clientHeight * 0.72);
  }
  scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
  await ymSleep(200);
}
if (!row || rowTrackId(row) !== wanted) { retreat(); return "fail"; }
if (row.scrollIntoView) row.scrollIntoView({ block: "center" });
await ymSleep(140);
if (action === "play") {
  const pauseInRow = row.querySelector('[data-test-id="PAUSE_BUTTON"]');
  if (pauseInRow && ymVisible(pauseInRow) && ymTransportPlaying()) return "playing";
  let button = null;
  for (const candidate of row.querySelectorAll('[data-test-id="PLAY_BUTTON"], button')) {
    if (!ymVisible(candidate)) continue;
    const id = candidate.getAttribute("data-test-id") || "";
    const label = candidate.getAttribute("aria-label") || "";
    if (id === "PLAY_BUTTON" || label.includes("Слушать") || label.includes("Воспроизведение")) { button = candidate; break; }
  }
  if (!button || forbidden(button) || !row.contains(button) || rowTrackId(row) !== wanted) { retreat(); return "fail"; }
  ymClick(button);
  for (let check = 0; check < 8; check++) {
    await ymSleep(140);
    const bar = ymById("PLAYERBAR_DESKTOP") || document;
    const link = bar.querySelector('a[href*="trackId=' + trackId + '"]');
    const pause = bar.querySelector('[data-test-id="PAUSE_BUTTON"]') || bar.querySelector('[aria-label="Пауза"]');
    if ((link && pause && ymVisible(pause)) || ymTransportPlaying()) return "playing";
  }
  retreat();
  return "fail";
}
let seenMenus = new Set();
function nearestMenu(menus) {
  const box = row.getBoundingClientRect();
  const ax = box.left + box.width / 2;
  const ay = box.top + box.height / 2;
  let best = null;
  let bestDist = Infinity;
  for (const menu of menus) {
    if (forbidden(menu) || !ymVisible(menu)) continue;
    const rect = menu.getBoundingClientRect();
    const dx = (rect.left + rect.width / 2) - ax;
    const dy = (rect.top + rect.height / 2) - ay;
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) { bestDist = dist; best = menu; }
  }
  return best;
}
function menuItem() {
  if (rowTrackId(row) !== wanted) return null;
  const all = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]')).filter((menu) => !forbidden(menu));
  const fresh = all.filter((menu) => !seenMenus.has(menu) && ymVisible(menu));
  const menu = fresh.length ? nearestMenu(fresh) : nearestMenu(all.filter((m) => ymVisible(m)));
  if (!menu || forbidden(menu)) return null;
  if (action === "next") {
    const found = ymById("TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON", menu) || ymById("TRACK_CONTEXT_MENU_PLAY_NEXT", menu);
    return found && menu.contains(found) && !forbidden(found) ? found : null;
  }
  const found = ymById("TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_QUEUE", menu)
    || menu.querySelector('[data-test-id*="ADD_TO_QUEUE"]');
  return found && menu.contains(found) && !forbidden(found) ? found : null;
}
function openRowMenu() {
  if (rowTrackId(row) !== wanted) return false;
  row.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
  row.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  let menuButton = null;
  for (const id of ["TRACK_CONTEXT_MENU_BUTTON", "TRACK_PLAYLIST_CONTEXT_MENU_BUTTON", "CONTEXT_MENU_BUTTON"]) {
    const found = ymById(id, row);
    if (found && row.contains(found) && !forbidden(found)) { menuButton = found; break; }
  }
  if (!menuButton) return false;
  seenMenus = new Set(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]'));
  ymClick(menuButton);
  return true;
}
let item = null;
for (let attempt = 0; attempt < 3 && !item; attempt++) {
  ymPressEscape();
  await ymSleep(80);
  if (!openRowMenu()) continue;
  await ymSleep(450);
  item = menuItem();
}
if (!item || rowTrackId(row) !== wanted || forbidden(item)) { ymPressEscape(); retreat(); return "no_menu"; }
ymClick(item);
await ymSleep(250);
ymPressEscape();
retreat();
return "ok";
""",
        ARTIST_ID=artist_id,
        MODE=mode,
        TRACK_ID=track_id,
        ALBUM_ID=album_id,
        INDEX=index,
        ACTION=action,
    )


def album_row_script(
    album_id: int,
    track_id: int,
    index: int | None,
    action: str,
) -> str:
    return fill(
        r"""
const albumId = String(__ALBUM_ID__);
const trackId = String(__TRACK_ID__);
const wanted = Number(trackId);
const index = __INDEX__;
const action = __ACTION__;
function albumPath() {
  return "/album?albumId=" + encodeURIComponent(albumId);
}
function onAlbum() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("trackId")) return false;
    if (url.searchParams.get("albumId") === albumId) return true;
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("album");
    return at >= 0 && parts[at + 1] === albumId && !parts.includes("track");
  } catch (error) { return false; }
}
function pageRoot() {
  return ymById("ALBUM_PAGE") || document.querySelector("main");
}
let opened = false;
function retreat() {
  if (opened && action !== "play") history.back();
}
function queueOpen() {
  const panel = ymById("PLAY_QUEUE");
  if (!panel) return false;
  const rect = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  return rect.width >= 2 && rect.height >= 2 && style.display !== "none" && style.visibility !== "hidden";
}
function queueToggle() {
  const panel = ymById("PLAY_QUEUE");
  const modal = ymById("FULLSCREEN_PLAYER_MODAL");
  const picks = [];
  if (panel && modal && modal.contains(panel)) {
    const full = ymById("FULLSCREEN_PLAYER_QUEUE_BUTTON");
    if (full) picks.push(full);
  }
  for (const el of document.querySelectorAll("button, [role='button']")) {
    const id = el.getAttribute("data-test-id") || "";
    if (id.indexOf("PLAY_QUEUE") === -1 || id === "PLAY_QUEUE") continue;
    picks.push(el);
  }
  const bar = ymById("PLAYERBAR_DESKTOP_PLAY_QUEUE_BUTTON");
  if (bar) picks.push(bar);
  return picks.find((el) => ymVisible(el)) || picks[0] || null;
}
if (queueOpen()) {
  for (let attempt = 0; attempt < 4 && queueOpen(); attempt++) {
    const toggle = queueToggle();
    if (!toggle) break;
    ymClick(toggle);
    await ymSleep(200);
  }
}
const wasHere = onAlbum();
await ymInAppGo(albumPath());
opened = !wasHere;
let ready = false;
for (let attempt = 0; attempt < 36; attempt++) {
  if (onAlbum() && pageRoot()) { ready = true; break; }
  if (attempt === 8 || attempt === 18) await ymInAppGo(albumPath());
  await ymSleep(150);
}
if (!ready) { retreat(); return "fail"; }
function numericId(anchor) {
  if (!anchor) return null;
  let url;
  try { url = new URL(anchor.getAttribute("href") || anchor.href, location.href); }
  catch (error) { return null; }
  const raw = url.searchParams.get("trackId");
  if (raw && /^\d+$/.test(raw)) return Number(raw);
  const parts = url.pathname.split("/");
  const at = parts.lastIndexOf("track");
  if (at >= 0 && /^\d+$/.test(parts[at + 1] || "")) return Number(parts[at + 1]);
  return null;
}
function forbidden(node) {
  return !!(node && node.closest && node.closest('[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"]'));
}
function rowTrackId(candidate) {
  const page = pageRoot();
  if (!candidate || !page || !page.contains(candidate) || forbidden(candidate)) return null;
  for (const anchor of candidate.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    const id = numericId(anchor);
    if (id != null) return id;
  }
  return null;
}
function findRow() {
  const page = pageRoot();
  if (!page) return null;
  for (const anchor of page.querySelectorAll('a[href*="trackId="], a[href*="/track/"]')) {
    if (forbidden(anchor)) continue;
    if (numericId(anchor) !== wanted) continue;
    const row = anchor.closest('[data-test-id="TRACK_ALBUM"], [data-test-id="TRACK_PLAYLIST"]');
    if (row && page.contains(row) && !forbidden(row) && rowTrackId(row) === wanted) return row;
  }
  return null;
}
function findScroller() {
  const page = pageRoot();
  if (!page) return null;
  const virtuoso = page.querySelector('[data-test-id="virtuoso-scroller"]');
  if (virtuoso) return virtuoso;
  const sample = page.querySelector('[data-test-id="TRACK_ALBUM"], [data-test-id="TRACK_PLAYLIST"]');
  let cur = sample ? sample.parentElement : page;
  while (cur && cur !== document.body) {
    const style = getComputedStyle(cur);
    const oy = style.overflowY;
    if ((oy === "auto" || oy === "scroll" || oy === "overlay") && cur.scrollHeight > cur.clientHeight + 4) return cur;
    cur = cur.parentElement;
  }
  return null;
}
let row = null;
let hinted = false;
for (let step = 0; step < 26; step++) {
  row = findRow();
  if (row) break;
  const scroller = findScroller();
  if (!scroller) { await ymSleep(180); continue; }
  const sample = document.querySelector('[data-test-id="TRACK_ALBUM"], [data-test-id="TRACK_PLAYLIST"]');
  const height = sample && sample.getBoundingClientRect().height > 20 ? sample.getBoundingClientRect().height : 56;
  if (!hinted && index != null && index > 0) {
    scroller.scrollTop = Math.max(0, (index - 2) * height);
    hinted = true;
  } else {
    scroller.scrollTop = scroller.scrollTop + Math.max(height * 8, scroller.clientHeight * 0.72);
  }
  scroller.dispatchEvent(new Event("scroll", { bubbles: true }));
  await ymSleep(200);
}
if (!row || rowTrackId(row) !== wanted) { retreat(); return "fail"; }
if (row.scrollIntoView) row.scrollIntoView({ block: "center" });
await ymSleep(140);
if (action === "play") {
  const pauseInRow = row.querySelector('[data-test-id="PAUSE_BUTTON"]');
  if (pauseInRow && ymVisible(pauseInRow) && ymTransportPlaying()) return "playing";
  let button = null;
  for (const candidate of row.querySelectorAll('[data-test-id="PLAY_BUTTON"], button')) {
    if (!ymVisible(candidate)) continue;
    const id = candidate.getAttribute("data-test-id") || "";
    const label = candidate.getAttribute("aria-label") || "";
    if (id === "PLAY_BUTTON" || label.includes("Слушать") || label.includes("Воспроизведение")) { button = candidate; break; }
  }
  if (!button || forbidden(button) || !row.contains(button) || rowTrackId(row) !== wanted) { retreat(); return "fail"; }
  ymClick(button);
  for (let check = 0; check < 8; check++) {
    await ymSleep(140);
    const bar = ymById("PLAYERBAR_DESKTOP") || document;
    const link = bar.querySelector('a[href*="trackId=' + trackId + '"]');
    const pause = bar.querySelector('[data-test-id="PAUSE_BUTTON"]') || bar.querySelector('[aria-label="Пауза"]');
    if ((link && pause && ymVisible(pause)) || ymTransportPlaying()) return "playing";
  }
  retreat();
  return "fail";
}
let seenMenus = new Set();
function nearestMenu(menus) {
  const box = row.getBoundingClientRect();
  const ax = box.left + box.width / 2;
  const ay = box.top + box.height / 2;
  let best = null;
  let bestDist = Infinity;
  for (const menu of menus) {
    if (forbidden(menu) || !ymVisible(menu)) continue;
    const rect = menu.getBoundingClientRect();
    const dx = (rect.left + rect.width / 2) - ax;
    const dy = (rect.top + rect.height / 2) - ay;
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) { bestDist = dist; best = menu; }
  }
  return best;
}
function menuItem() {
  if (rowTrackId(row) !== wanted) return null;
  const all = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]')).filter((menu) => !forbidden(menu));
  const fresh = all.filter((menu) => !seenMenus.has(menu) && ymVisible(menu));
  const menu = fresh.length ? nearestMenu(fresh) : nearestMenu(all.filter((m) => ymVisible(m)));
  if (!menu || forbidden(menu)) return null;
  if (action === "next") {
    const found = ymById("TRACK_CONTEXT_MENU_PLAY_NEXT_BUTTON", menu) || ymById("TRACK_CONTEXT_MENU_PLAY_NEXT", menu);
    return found && menu.contains(found) && !forbidden(found) ? found : null;
  }
  const found = ymById("TRACK_CONTEXT_MENU_PLAY_LAST_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE", menu)
    || ymById("TRACK_CONTEXT_MENU_ADD_TO_QUEUE_BUTTON", menu)
    || ymById("TRACK_CONTEXT_MENU_QUEUE", menu)
    || menu.querySelector('[data-test-id*="ADD_TO_QUEUE"]');
  return found && menu.contains(found) && !forbidden(found) ? found : null;
}
function openRowMenu() {
  if (rowTrackId(row) !== wanted) return false;
  row.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
  row.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  let menuButton = null;
  for (const id of ["TRACK_CONTEXT_MENU_BUTTON", "TRACK_PLAYLIST_CONTEXT_MENU_BUTTON", "CONTEXT_MENU_BUTTON"]) {
    const found = ymById(id, row);
    if (found && row.contains(found) && !forbidden(found)) { menuButton = found; break; }
  }
  if (!menuButton) return false;
  seenMenus = new Set(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"]'));
  ymClick(menuButton);
  return true;
}
let item = null;
for (let attempt = 0; attempt < 3 && !item; attempt++) {
  ymPressEscape();
  await ymSleep(80);
  if (!openRowMenu()) continue;
  await ymSleep(450);
  item = menuItem();
}
if (!item || rowTrackId(row) !== wanted || forbidden(item)) { ymPressEscape(); retreat(); return "no_menu"; }
ymClick(item);
await ymSleep(250);
ymPressEscape();
retreat();
return "ok";
""",
        ALBUM_ID=album_id,
        TRACK_ID=track_id,
        INDEX=index,
        ACTION=action,
    )


def wave_background_script() -> str:
    """Фон карточки «Моя волна» на уже открытой главной. Страницу не переключает."""
    return script(
        r"""
function homeWaveNode(root) {
  if (!root) return null;
  let best = null;
  let bestArea = Infinity;
  const nodes = root.querySelectorAll("[data-test-id], a, button, article, section, div");
  for (const node of nodes) {
    const text = ymText(node).replace(/\s+/g, " ").trim().toLowerCase();
    const id = (node.getAttribute("data-test-id") || "").toUpperCase();
    if (!text && !id) continue;
    if (text.includes("люмен") || id.includes("LUMEN") || id.includes("PLAYER") || id.includes("QUEUE")) continue;
    const home = text.startsWith("моя волна") || id.includes("MY_WAVE") || id.includes("VIBE_BUTTON") || id.includes("PERSONAL_VIBE");
    if (!home) continue;
    const rect = node.getBoundingClientRect();
    const area = rect.width * rect.height;
    if (area < 40 || area >= bestArea) continue;
    best = node;
    bestArea = area;
  }
  return best;
}
const card = homeWaveNode(document.querySelector("main") || document.body);
if (!card) return { ok: false };
const art = ymCardArt(card);
return { ok: true, cover: art.cover || "", background: art.background || "" };
"""
    )


def personal_wave_script(card_title: str | None = None, card_index: int | None = None) -> str:
    """Карточка в уже открытой выдаче, иначе карточка на главной десктопа.

    card_title или card_index кликают конкретную строку волны в открытом поиске.
    """
    return fill(
        r"""
const wantTitle = String(__CARD_TITLE__ || "").trim().toLowerCase();
const wantIndex = __CARD_INDEX__;
function folded(el) {
  return ymText(el).replace(/\s+/g, " ").trim().toLowerCase();
}
function isLumenText(text) {
  return text.includes("люмен");
}
function isWaveText(text) {
  return text.includes("моя волна") && !isLumenText(text);
}
function clickable(el) {
  if (!el) return null;
  const inner = el.matches && el.matches("a,button") ? el : el.querySelector("a,button");
  const target = inner || el;
  return ymVisible(target, 8) ? target : (ymVisible(el, 8) ? el : null);
}
function waveCards(root) {
  const found = [];
  if (!root) return found;
  const lumenNode = ymById("QUERY_TO_VIBE_BLOCK", root);
  for (const node of root.querySelectorAll('[data-test-id="SEARCH_VIBE_CARD"]')) {
    if (lumenNode && lumenNode.contains(node)) continue;
    const titleEl = ymById("ENTITY_CARD_ENTITY_META_TITLE", node);
    const title = (titleEl ? ymText(titleEl) : "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!title || title === "моя волна") continue;
    const play = node.querySelector('[data-test-id="PLAY_BUTTON"]');
    const target = (play && ymVisible(play, 8)) ? play : clickable(node);
    if (!target) continue;
    found.push({ title, el: target });
  }
  return found;
}
function homeCard(root) {
  if (!root) return null;
  const nodes = root.querySelectorAll("[data-test-id], a, button, article, section");
  for (const node of nodes) {
    const text = folded(node);
    const id = (node.getAttribute("data-test-id") || "").toUpperCase();
    if (isLumenText(text) || id.includes("PLAYER") || id.includes("QUEUE")) continue;
    const home = text.startsWith("моя волна") || id.includes("MY_WAVE") || id.includes("VIBE_BUTTON") || id.includes("PERSONAL_VIBE");
    if (!home) continue;
    const target = clickable(node);
    if (target) return target;
  }
  return null;
}
const aimed = !!(wantTitle || (typeof wantIndex === "number" && wantIndex >= 0));
const searchPage = ymById("SEARCH_PAGE");
if (aimed) {
  if (!searchPage) return "fail";
  const cards = waveCards(searchPage);
  let card = null;
  if (wantTitle) card = cards.find((item) => item.title === wantTitle) || null;
  if (!card && typeof wantIndex === "number" && wantIndex >= 0) card = cards[wantIndex] || null;
  if (!card) return "fail";
  ymClick(card.el);
  return "started";
}
if (!location.pathname.includes("/collection")) await ymInAppGo("/collection");
let likesPath = "";
for (let step = 0; step < 25 && !likesPath; step++) {
  const block = ymById("COLLECTION_PLAYLIST_WITH_LIKES");
  const link = block && block.querySelector('a[href*="playlistUuid="]');
  const href = link ? (link.getAttribute("href") || "") : "";
  const match = href.match(/playlistUuid=([^&]+)/);
  if (match) likesPath = "/playlists?playlistUuid=" + match[1];
  else await ymSleep(200);
}
if (!likesPath) return "fail";
const likesKey = likesPath.split("playlistUuid=")[1];
if (!location.href.includes(likesKey)) await ymInAppGo(likesPath);
for (let step = 0; step < 30; step++) {
  await ymSleep(200);
  if (!location.href.includes(likesKey)) {
    if (step === 8) await ymInAppGo(likesPath);
    continue;
  }
  const header = ymById("ENTITY_HEADER") || document.querySelector("main");
  const menuButton = header && ymById("PLAYLIST_HEADER_CONTEXT_MENU_BUTTON", header);
  if (!menuButton || !ymVisible(menuButton, 8)) continue;
  ymClick(menuButton);
  await ymSleep(480);
  const menus = Array.from(document.querySelectorAll('[role="menu"]')).filter((menu) => ymVisible(menu, 8));
  const item = (menus[0] || document).querySelector('[data-test-id="CONTEXT_MENU_VIBE_BUTTON"]');
  if (!item || !ymVisible(item, 8)) { ymPressEscape(); continue; }
  const label = ymText(item).replace(/\s+/g, " ").trim().toLowerCase();
  if (label.includes("по треку")) { ymPressEscape(); continue; }
  const key = Object.keys(item).find((name) => name.startsWith("__reactProps"));
  const handler = key && item[key] && item[key].onClick;
  if (typeof handler === "function") {
    try {
      handler({
        preventDefault() {},
        stopPropagation() {},
        nativeEvent: { stopPropagation() {} },
        currentTarget: item,
        target: item,
        button: 0,
        type: "click",
      });
    } catch (error) {}
  }
  ymClick(item);
  return "started";
}
return "fail";
""",
        CARD_TITLE=card_title or "",
        CARD_INDEX=card_index,
    )


def current_wave_script() -> str:
    return script(
        r"""
const bar = ymById("PLAYERBAR_DESKTOP") || ymById("FULLSCREEN_PLAYER_MODAL") || ymById("VIBE_PLAYERBAR");
if (!bar) return "no_track";
const title = ymText(ymById("TRACK_TITLE", bar)) || ymText(ymById("VIBE_PLAYERBAR_TRACK_NAME", bar)) || ymText(ymById("VIBE_PLAYERBAR_TRACK_NAME"));
if (!title) return "no_track";
function waveLabel(el) {
  const id = ((el && el.getAttribute("data-test-id")) || "").toUpperCase();
  const text = (((el && el.getAttribute("aria-label")) || "") + " " + ymText(el)).replace(/\s+/g, " ").trim().toLowerCase();
  if (id.includes("LUMEN") || text.includes("люмен")) return false;
  return text.includes("волн") || id.includes("VIBE_CONTEXT") || id.includes("TRACK_VIBE") || id.includes("MY_WAVE");
}
function visibleWave(root) {
  if (!root) return null;
  const named = root.querySelector('[data-test-id="CONTEXT_MENU_VIBE_BUTTON"]');
  if (named && waveLabel(named) && ymVisible(named, 8)) return named;
  const hits = [];
  for (const el of root.querySelectorAll("button, a, [role='button'], [data-test-id]")) {
    if (!waveLabel(el) || !ymVisible(el, 8)) continue;
    hits.push(el);
  }
  const leaf = hits.find((el) => !hits.some((other) => other !== el && el.contains(other)));
  return leaf || null;
}
let button = visibleWave(bar);
if (button) { ymClick(button); return "started"; }
const menuButton = ymById("CONTEXT_MENU_BUTTON", bar) || ymById("TRACK_CONTEXT_MENU_BUTTON", bar) || bar.querySelector('[aria-label*="ещё"], [aria-label*="меню"]');
if (menuButton && ymVisible(menuButton, 8)) {
  ymClick(menuButton);
  await ymSleep(450);
  const menus = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"], [role="menu"]')).filter((menu) => ymVisible(menu));
  button = visibleWave(menus[0] || document.body);
  if (button) { ymClick(button); return "started"; }
  ymPressEscape();
}
return "fail";
"""
    )


def _entity_wave_script(body: str, **values: object) -> str:
    shared = r"""
function waveLabel(el) {
  const id = ((el && el.getAttribute("data-test-id")) || "").toUpperCase();
  const text = (((el && el.getAttribute("aria-label")) || "") + " " + ymText(el)).replace(/\s+/g, " ").trim().toLowerCase();
  if (!text.includes("волн") && !id.includes("VIBE") && !id.includes("MY_WAVE") && !id.includes("WAVE")) return false;
  if (id.includes("PLAYER") || id.includes("QUEUE") || id.includes("RESET_VIBE") || text.includes("люмен")) return false;
  return true;
}
function visibleWave(root) {
  if (!root) return null;
  const named = root.querySelector('[data-test-id="CONTEXT_MENU_VIBE_BUTTON"]');
  if (named && waveLabel(named) && ymVisible(named, 8)) return named;
  const hits = [];
  for (const el of root.querySelectorAll("button, a, [role='menuitem'], [role='button'], [data-test-id]")) {
    if (!waveLabel(el) || !ymVisible(el, 8)) continue;
    if (el.closest('[data-test-id="PLAY_QUEUE"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="FULLSCREEN_PLAYER_MODAL"], [data-test-id="VIBE_PLAYERBAR"]')) continue;
    hits.push(el);
  }
  const leaf = hits.find((el) => !hits.some((other) => other !== el && el.contains(other)));
  return leaf || null;
}
async function pressHeaderWave(menuId) {
  const header = ymById("ENTITY_HEADER") || document.querySelector("main");
  const menuButton = (header && ymById(menuId, header)) || (header && header.querySelector('[data-test-id$="HEADER_CONTEXT_MENU_BUTTON"]'));
  if (!menuButton || !ymVisible(menuButton, 8)) return false;
  if (menuButton.closest('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"], [data-test-id="virtuoso-item-list"]')) return false;
  ymClick(menuButton);
  await ymSleep(480);
  const menus = Array.from(document.querySelectorAll('[role="menu"]')).filter((menu) => ymVisible(menu, 8));
  const item = visibleWave(menus[0] || null);
  if (!item) { ymPressEscape(); return false; }
  const label = ymText(item).replace(/\s+/g, " ").trim().toLowerCase();
  if (label.includes("по треку")) { ymPressEscape(); return false; }
  const key = Object.keys(item).find((name) => name.startsWith("__reactProps"));
  const handler = key && item[key] && item[key].onClick;
  if (typeof handler === "function") {
    try {
      handler({
        preventDefault() {},
        stopPropagation() {},
        nativeEvent: { stopPropagation() {} },
        currentTarget: item,
        target: item,
        button: 0,
        type: "click",
      });
    } catch (error) {}
  }
  ymClick(item);
  return true;
}
async function pressWave(scope) {
  const menuButton = (scope && ymById("TRACK_HEADER_CONTEXT_MENU_BUTTON", scope)) || ymById("TRACK_HEADER_CONTEXT_MENU_BUTTON");
  if (!menuButton || !ymVisible(menuButton, 8)) return false;
  ymClick(menuButton);
  await ymSleep(480);
  const menus = Array.from(document.querySelectorAll('[data-test-id="TRACK_CONTEXT_MENU"], [role="menu"]')).filter((menu) => ymVisible(menu));
  const item = visibleWave(menus[0] || document.body);
  if (!item) { ymPressEscape(); return false; }
  ymClick(item);
  return true;
}
"""
    return fill(shared + body, **values)


def track_wave_script(track_id: int, album_id: int) -> str:
    return _entity_wave_script(
        r"""
const trackId = String(__TRACK_ID__);
const albumId = String(__ALBUM_ID__);
function onTrackPage() {
  const href = location.href;
  return href.includes("trackId=" + trackId) && href.includes("albumId=" + albumId);
}
if (!onTrackPage()) {
  await ymInAppGo("/album/track?albumId=" + encodeURIComponent(albumId) + "&trackId=" + encodeURIComponent(trackId));
}
for (let step = 0; step < 40; step++) {
  await ymSleep(250);
  if (step === 8 && !onTrackPage()) {
    await ymInAppGo("/album/track?albumId=" + encodeURIComponent(albumId) + "&trackId=" + encodeURIComponent(trackId));
  }
  if (!onTrackPage()) continue;
  const page = ymById("TRACK_PAGE") || document.querySelector("main");
  if (await pressWave(page)) return "started";
}
return "fail";
""",
        TRACK_ID=track_id,
        ALBUM_ID=album_id,
    )


def artist_wave_script(artist_id: int) -> str:
    return _entity_wave_script(
        r"""
const artistId = String(__ARTIST_ID__);
function onArtist() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("artistId") === artistId) {
      return !url.pathname.includes("/tracks") && !url.pathname.includes("/familiar");
    }
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("artist");
    return at >= 0 && parts[at + 1] === artistId && parts.length === at + 2;
  } catch (error) { return false; }
}
if (!onArtist()) await ymInAppGo("/artist?artistId=" + encodeURIComponent(artistId));
for (let step = 0; step < 40; step++) {
  await ymSleep(250);
  if (step === 8 && !onArtist()) await ymInAppGo("/artist/" + encodeURIComponent(artistId));
  if (!onArtist()) continue;
  if (await pressHeaderWave("ARTIST_HEADER_CONTEXT_MENU_BUTTON")) return "started";
}
return "fail";
""",
        ARTIST_ID=artist_id,
    )


def album_wave_script(album_id: int) -> str:
    return _entity_wave_script(
        r"""
const albumId = String(__ALBUM_ID__);
function onAlbum() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("trackId")) return false;
    if (url.searchParams.get("albumId") === albumId) return true;
    const parts = url.pathname.split("/").filter(Boolean);
    const at = parts.lastIndexOf("album");
    return at >= 0 && parts[at + 1] === albumId && !parts.includes("track");
  } catch (error) { return false; }
}
if (!onAlbum()) await ymInAppGo("/album?albumId=" + encodeURIComponent(albumId));
for (let step = 0; step < 40; step++) {
  await ymSleep(250);
  if (step === 8 && !onAlbum()) await ymInAppGo("/album/" + encodeURIComponent(albumId));
  if (!onAlbum()) continue;
  if (await pressHeaderWave("ALBUM_HEADER_CONTEXT_MENU_BUTTON")) return "started";
}
return "fail";
""",
        ALBUM_ID=album_id,
    )


def playlist_wave_script(playlist_uuid: str, playlist_kind: int | None, playlist_uid: int | None) -> str:
    return _entity_wave_script(
        r"""
const playlistUuid = String(__PLAYLIST_UUID__);
const playlistKind = __PLAYLIST_KIND__ == null ? "" : String(__PLAYLIST_KIND__);
const playlistUid = __PLAYLIST_UID__ == null ? "" : String(__PLAYLIST_UID__);
function onPlaylist() {
  try {
    const url = new URL(location.href);
    if (url.searchParams.get("playlistUuid") === playlistUuid) return true;
    if (playlistKind && playlistUid) {
      return url.pathname.includes("/users/" + playlistUid + "/playlists/" + playlistKind);
    }
    return false;
  } catch (error) { return false; }
}
function openPlaylist() {
  return "/playlists?playlistUuid=" + encodeURIComponent(playlistUuid);
}
if (!onPlaylist()) await ymInAppGo(openPlaylist());
for (let step = 0; step < 40; step++) {
  await ymSleep(250);
  if (step === 8 && !onPlaylist()) await ymInAppGo("/playlists?playlistUuid=" + encodeURIComponent(playlistUuid));
  if (!onPlaylist()) continue;
  if (await pressHeaderWave("PLAYLIST_HEADER_CONTEXT_MENU_BUTTON")) return "started";
}
return "fail";
""",
        PLAYLIST_UUID=playlist_uuid,
        PLAYLIST_KIND=playlist_kind,
        PLAYLIST_UID=playlist_uid,
    )


def lumen_script(prompt: str) -> str:
    return fill(
        r"""
const prompt = __PROMPT__;
function isLumen(el) {
  if (!el) return false;
  const id = (el.getAttribute("data-test-id") || "").toUpperCase();
  const text = (((el.getAttribute("aria-label") || "") + " " + ymText(el)).replace(/\s+/g, " ").trim().toLowerCase());
  if (el.closest && el.closest('[data-test-id="SEARCH_TRACK_CARD"], [data-test-id="PLAYERBAR_DESKTOP"], [data-test-id="VIBE_PLAYERBAR"]')) return false;
  return id.includes("LUMEN") || text.includes("люмен");
}
function lumenCard(root) {
  if (!root) return null;
  const exact = ymById("QUERY_TO_VIBE_BLOCK", root);
  if (exact && ymVisible(exact, 8)) return exact;
  const wanted = String(prompt || "").trim().toLowerCase();
  const nodes = root.querySelectorAll("a, button, li, article, [data-test-id]");
  const matches = [];
  for (const node of nodes) {
    if (!isLumen(node)) continue;
    let deeper = false;
    for (const child of node.querySelectorAll("a, button, li, article")) {
      if (child !== node && isLumen(child)) { deeper = true; break; }
    }
    if (deeper) continue;
    matches.push(node);
  }
  if (wanted) {
    const named = matches.find((node) => ymText(node).toLowerCase().includes(wanted));
    if (named) return named;
  }
  return matches[0] || null;
}
async function ensureSearch() {
  const page = ymById("SEARCH_PAGE");
  if (page && ymVisible(page, 8)) return page;
  const nav = ymById("NAVBAR_NAVIGATION_ITEM_SEARCH");
  if (nav) ymClick(nav);
  for (let attempt = 0; attempt < 20; attempt++) {
    await ymSleep(150);
    const opened = ymById("SEARCH_PAGE");
    if (opened) return opened;
  }
  return null;
}
const page = await ensureSearch();
if (!page) return "fail";
let card = null;
for (let step = 0; step < 20 && !card; step++) {
  card = lumenCard(page) || lumenCard(document.querySelector("main"));
  if (!card) await ymSleep(200);
}
if (!card) return "fail";
const opener = card.matches && card.matches("a,button") ? card : (card.querySelector("a,button") || card);
ymClick(opener);
let field = null;
for (let step = 0; step < 8 && !field; step++) {
  await ymSleep(200);
  const scope = card || document;
  field = scope.querySelector("textarea, input[type='text'], input:not([type='hidden'])");
  if (!field) field = document.querySelector('[data-test-id*="LUMEN"] textarea, [data-test-id*="LUMEN"] input');
  if (field && document.activeElement && document.activeElement !== field && step < 3) field = null;
}
if (!field) return "started";
if (!ymSetNativeValue(field, prompt)) return "started";
const host = field.closest("form, [data-test-id*='LUMEN'], article, section") || document;
let listen = null;
for (const button of host.querySelectorAll("button")) {
  const label = ((button.getAttribute("aria-label") || "") + " " + ymText(button)).toLowerCase();
  if (label.includes("слушать") || label.includes("включить") || label.includes("запустить")) { listen = button; break; }
}
if (!listen) return "fail";
ymClick(listen);
return "started";
""",
        PROMPT=prompt,
    )
