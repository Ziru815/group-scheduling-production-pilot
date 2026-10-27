/** "20% travel · 80% attendance" (FR-D9: the split shown as text). */
export function weightSplitText(attendancePercent: number) {
  return `${100 - attendancePercent}% travel · ${attendancePercent}% attendance`
}
