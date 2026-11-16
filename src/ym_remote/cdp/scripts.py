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
  return el && el.textContent ? el.textContent.trim() : "";
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
const artistRoot = ymById("PLAYERBAR_DESKTOP") || bar;
let artists = Array.from(artistRoot.querySelectorAll('[data-test-id="SEPARATED_ARTIST_TITLE"]')).map((el) => ymText(el)).filter(Boolean);
let cover = "";
const coverRoot = ymById("ENTITY_COVER_IMAGE", bar) || ymById("ENTITY_COVER_IMAGE");
if (coverRoot) {
  const img = coverRoot.matches && coverRoot.matches("img") ? coverRoot : coverRoot.querySelector("img");
  cover = (img || coverRoot).getAttribute("src") || "";
}
let isPlaying = ymTransportPlaying();
if (!title && navigator.mediaSession && navigator.mediaSession.metadata) {
  const meta = navigator.mediaSession.metadata;
  title = meta.title || "";
  if (!artists.length && meta.artist) artists = [meta.artist];
  if (!cover && meta.artwork && meta.artwork.length) cover = meta.artwork[0].src || "";
  isPlaying = navigator.mediaSession.playbackState === "playing";
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
const artistLink = (ymById("PLAYERBAR_DESKTOP") || document).querySelector('[data-test-id="SEPARATED_ARTIST_TITLE"] a');
if (artistLink) artistHref = artistLink.href || null;
let artistRefs = ymReadArtistRefs(artistRoot);
if (!artistRefs.length && artists.length) {
  artistRefs = artists.map((name) => ({ id: null, name }));
}
let albumHref = null;
const coverBox = ymById("PLAYERBAR_DESKTOP_COVER_CONTAINER");
const albumLink = coverBox && coverBox.querySelector("a");
if (albumLink) albumHref = albumLink.href || null;
if (!albumHref) {
  const coverButton = ymById("ENTITY_COVER_BUTTON");
  if (coverButton && coverButton.href) albumHref = coverButton.href;
}
let queueName = "";
const nameIds = ["FULLSCREEN_PLAYER_CONTEXT_TITLE", "FULLSCREEN_PLAYER_HEADER_TITLE", "PLAYER_CONTEXT_TITLE", "CONTEXT_TITLE", "PLAY_QUEUE_NOW_PLAYING_BLOCK_TITLE"];
const modal = ymById("FULLSCREEN_PLAYER_MODAL");
for (const id of nameIds) {
  const el = (modal && ymById(id, modal)) || ymById(id);
  if (el && ymText(el)) { queueName = ymText(el); break; }
}
if (!queueName) {
  const scope = ymById("PLAYERBAR_DESKTOP") || document;
  const links = scope.querySelectorAll('a[href*="playlist"], a[href*="album"], a[href*="artist"]');
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
  shuffle, liked, artist_href: artistHref, album_href: albumHref, queue_name: queueName
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
const bar = ymById("PLAYERBAR_DESKTOP");
if (target === "artist") {
  const link = bar && bar.querySelector('[data-test-id="SEPARATED_ARTIST_TITLE"] a');
  if (!link) return false;
  ymClick(link);
  return true;
}
const box = ymById("PLAYERBAR_DESKTOP_COVER_CONTAINER");
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
return { ok: true, tracks, artist_cards: artistCards };
""",
        QUERY=query,
    )


def queue_script(mode: str, track_id: int | None = None) -> str:
    return fill(
        r"""
const mode = __MODE__;
const trackId = __TRACK_ID__ == null ? "" : String(__TRACK_ID__);
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
if (mode === "read") {
  if (!(await ensureQueue(350))) return empty;
  return readQueue();
}
if (!(await ensureQueue(500))) return { ok: false, code: "fail" };
const panel = ymById("PLAY_QUEUE");
let row = null;
for (const candidate of panel.querySelectorAll('[data-test-id="TRACK_PLAYLIST"], [data-test-id="TRACK_ALBUM"]')) {
  const anchor = candidate.querySelector('a[href*="trackId="]');
  if (!anchor) continue;
  try {
    const url = new URL(anchor.href, location.href);
    if (url.searchParams.get("trackId") === trackId) { row = candidate; break; }
  } catch (error) {}
}
if (!row) return { ok: false, code: "fail" };
if (row.querySelector('[data-test-id="PAUSE_BUTTON"]')) {
  const view = readQueue();
  view.code = "already";
  return view;
}
if (row.scrollIntoView) row.scrollIntoView({ block: "center" });
await ymSleep(80);
const button = row.querySelector('[data-test-id="PLAY_BUTTON"]');
if (!button) return { ok: false, code: "fail" };
ymClick(button);
await ymSleep(180);
const view = readQueue();
view.code = "playing";
return view;
""",
        MODE=mode,
        TRACK_ID=track_id,
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
