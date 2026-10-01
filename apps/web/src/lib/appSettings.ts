import { useEffect, useState } from 'react'
import { api } from './api'
import type { AppSettings } from './types'

// Server-side settings (shared by every screen). Fetched once, refreshed after the Settings page saves.
let cache: AppSettings | null = null
let inflight: Promise<AppSettings> | null = null
const listeners = new Set<(s: AppSettings) => void>()

export function loadSettings(force = false): Promise<AppSettings> {
  if (cache && !force) return Promise.resolve(cache)
  if (!inflight || force)
    inflight = api
      .settings()
      .then((s) => {
        setSettingsCache(s)
        return s
      })
      .catch((e) => {
        inflight = null // a failed request is not cached: the next caller tries again
        throw e
      })
  return inflight
}

export function setSettingsCache(s: AppSettings) {
  cache = s
  listeners.forEach((l) => l(s))
}

export function useAppSettings(): AppSettings | null {
  const [s, setS] = useState<AppSettings | null>(cache)
  useEffect(() => {
    listeners.add(setS)
    loadSettings().catch(() => undefined)
    return () => {
      listeners.delete(setS)
    }
  }, [])
  return s
}

export function useThreshold(): number {
  return useAppSettings()?.confidence_threshold ?? 0.75
}

// Local (this browser only) interface preferences.
const MOTION_KEY = 'tsekmate.reduceMotion'

export function getReduceMotion(): boolean {
  try {
    return localStorage.getItem(MOTION_KEY) === '1'
  } catch {
    return false
  }
}

export function setReduceMotion(on: boolean) {
  try {
    localStorage.setItem(MOTION_KEY, on ? '1' : '0')
  } catch {
    /* storage blocked: applies to this page view only */
  }
  applyMotionPreference(on)
}

export function applyMotionPreference(on = getReduceMotion()) {
  document.documentElement.classList.toggle('reduce-motion', on)
}
