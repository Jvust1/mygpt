export const DEFAULT_PROFILE = Object.freeze({
  policy: {
    supervisionWeight: 0.7,
    companionshipWeight: 0.3,
    defaultMode: "companion",
    checkInMinutes: 25,
    cooldownMinutes: 8,
  },
  thresholds: {
    light: 0.2,
    firm: 0.45,
    focus: 0.7,
  },
  live: {
    defaultEmotion: "neutral",
    supervisionEmotion: "focused",
    completionEmotion: "happy",
  },
});

export function validateProfile(profile = DEFAULT_PROFILE) {
  const s = profile.policy?.supervisionWeight;
  const c = profile.policy?.companionshipWeight;
  if (!Number.isFinite(s) || !Number.isFinite(c) || s < 0 || c < 0) {
    throw new TypeError("supervisionWeight and companionshipWeight must be non-negative numbers");
  }
  if (Math.abs(s + c - 1) > 1e-9) {
    throw new RangeError("supervisionWeight + companionshipWeight must equal 1");
  }
  const { light, firm, focus } = profile.thresholds ?? {};
  if (![light, firm, focus].every(Number.isFinite) || !(0 <= light && light < firm && firm < focus && focus <= 1)) {
    throw new RangeError("thresholds must satisfy 0 <= light < firm < focus <= 1");
  }
  return profile;
}
