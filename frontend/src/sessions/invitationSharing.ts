import type { IsoDate, IsoDateTime, TimeZone } from '../api/types'
import { formatDateTime, formatIsoDate } from '../lib/time.ts'

export type InvitationMessageInput = {
  name: string
  activityName: string
  startDate: IsoDate
  endDate: IsoDate
  responseDeadline: IsoDateTime
  timezone: TimeZone
  invitationUrl: string
}

export function buildInvitationMessage(input: InvitationMessageInput): string {
  const dates =
    input.startDate === input.endDate
      ? formatIsoDate(input.startDate)
      : `${formatIsoDate(input.startDate)} – ${formatIsoDate(input.endDate)}`

  return [
    `You're invited to “${input.name}”`,
    `Activity: ${input.activityName}`,
    `Dates: ${dates}`,
    `Respond by: ${formatDateTime(input.responseDeadline, input.timezone)}`,
    `Join and mark when you're free: ${input.invitationUrl}`,
  ].join('\n')
}
