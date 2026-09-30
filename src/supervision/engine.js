import { DEFAULT_PROFILE, validateProfile } from "../config/profile.js";

const clamp01 = (value) => Math.max(0, Math.min(1, Number(value) || 0));
const normalizeMinutes = (value, max) => clamp01((Number(value) || 0) / max);

export class SupervisionEngine {
  constructor(profile = DEFAULT_PROFILE) {
    this.profile = validateProfile(profile);
  }

  evaluate(signal = {}) {
    if (signal.completed) {
      return {
        mode: "companion",
        score: 0,
        reason: "completed",
        emotion: this.profile.live.completionEmotion,
        nextCheckInMinutes: null,
      };
    }

    if (!signal.taskActive) {
      return {
        mode: "companion",
        score: 0,
        reason: "no-active-task",
        emotion: this.profile.live.defaultEmotion,
        nextCheckInMinutes: this.profile.policy.checkInMinutes,
      };
    }

    const raw =
      normalizeMinutes(signal.overdueMinutes, 45) * 0.35 +
      normalizeMinutes(signal.idleMinutes, 30) * 0.25 +
      clamp01(signal.focusDrift) * 0.25 +
      clamp01((signal.missedCheckIns || 0) / 3) * 0.15;

    const breakCredit = signal.onApprovedBreak ? 0.45 : 0;
    const score = clamp01(
      (raw - breakCredit) * (0.5 + this.profile.policy.supervisionWeight * 0.5),
    );

    const { light, firm, focus } = this.profile.thresholds;
    let mode = "companion";
    if (score >= focus) mode = "focus";
    else if (score >= firm) mode = "firm";
    else if (score >= light) mode = "light";

    return {
      mode,
      score: Number(score.toFixed(3)),
      reason: this.#reason(signal, mode),
      emotion: mode === "companion"
        ? this.profile.live.defaultEmotion
        : this.profile.live.supervisionEmotion,
      nextCheckInMinutes: mode === "focus" ? 10 : this.profile.policy.checkInMinutes,
    };
  }

  #reason(signal, mode) {
    if (mode === "companion") return "on-track";
    const cues = [];
    if ((signal.overdueMinutes || 0) > 0) cues.push("overdue");
    if ((signal.idleMinutes || 0) >= 10) cues.push("idle");
    if ((signal.focusDrift || 0) >= 0.5) cues.push("focus-drift");
    if ((signal.missedCheckIns || 0) > 0) cues.push("missed-checkin");
    return cues.join("+") || "supervision-policy";
  }
}
