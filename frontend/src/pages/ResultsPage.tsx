import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { isApiError } from '../api/client'
import { useConfirmPlan, useGenerateRecommendations, useRecommendations } from '../api/hooks/recommendations'
import { useSession } from '../api/hooks/sessions'
import type { ExclusionReason, RecommendationSet, SessionDetail } from '../api/types'
import { StatusMessage } from '../components/StatusMessage'
import { formatTime } from '../lib/time'
import { ConfirmPlanPanel } from '../results/ConfirmPlanPanel'
import {
  chooseRecommendationTime,
  groupRankedCombinations,
  selectedOptionForGroup,
} from '../results/groupRecommendations'
import { RankedOptionCard } from '../results/RankedOptionCard'
import { GenerateError } from '../sessions/GenerateError'
import { OBJECTIVE_LABELS } from '../sessions/labels'
import { ScoringControls } from '../sessions/ScoringControls'
import { weightSplitText } from '../sessions/scoring'
import './ResultsPage.css'

const EXCLUSION_LABELS: Record<ExclusionReason, string> = {
  BELOW_THRESHOLD: 'too few people free',
  JOURNEY_LIMIT: 'someone’s journey too long',
  GROUP_SIZE: 'group too small for the venue',
  BOOKING_LEAD_TIME: 'too late to book',
}

/**
 * Best matches (SRS §3.1; UC-11 view, UC-12 confirm; FR-E1 to FR-E4). Any
 * member can view; only the Organiser can generate, re-rank or confirm.
 */
export function ResultsPage() {
  const { id } = useParams()
  const session = useSession(id)
  const recs = useRecommendations(id)

  if (session.isPending || recs.isPending) return <StatusMessage busy title="Loading options…" />

  const error = session.error ?? recs.error
  if (error) {
    const missing = isApiError(error) && error.status === 404
    return (
      <StatusMessage
        title={missing ? "We couldn't find that session" : "Couldn't load the options"}
        action={
          missing ? (
            <Link className="btn-primary" to="/sessions">
              Back to your sessions
            </Link>
          ) : (
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                void session.refetch()
                void recs.refetch()
              }}
            >
              Try again
            </button>
          )
        }
      >
        {missing ? "It may have been removed, or you haven't joined it." : error.message}
      </StatusMessage>
    )
  }

  return (
    <ResultsView
      session={session.data!}
      set={recs.data ?? null}
      refreshSession={() => void session.refetch()}
    />
  )
}

function ResultsView({
  session,
  set,
  refreshSession,
}: {
  session: SessionDetail
  set: RecommendationSet | null
  refreshSession: () => void
}) {
  const navigate = useNavigate()
  const generate = useGenerateRecommendations(session.id)
  const confirm = useConfirmPlan(session.id)
  const isOrganiser = session.myRole === 'ORGANISER'
  const active = session.status === 'ACTIVE'
  const mutable = active && session.activitySupported
  const stale = Boolean(set?.stale || session.recommendationsStale)

  const combos = set?.combinations ?? []
  const groups = useMemo(() => groupRankedCombinations(set?.combinations ?? []), [set?.combinations])

  // undefined = default to the top group; null = user collapsed everything.
  const [expandedGroupKey, setExpandedGroupKey] = useState<string | null | undefined>(undefined)
  const [selectedByGroup, setSelectedByGroup] = useState<Record<string, string>>({})
  const [confirming, setConfirming] = useState(false)

  const expandedGroup =
    expandedGroupKey === null ? null : (groups.find((group) => group.key === expandedGroupKey) ?? groups[0] ?? null)
  const expanded =
    expandedGroup === null
      ? null
      : selectedOptionForGroup(
          expandedGroup,
          selectedByGroup[expandedGroup.key],
          session.confirmed?.combinationId,
        )

  function toggle(groupKey: string) {
    if (confirm.isPending) return
    setConfirming(false)
    confirm.reset()
    setExpandedGroupKey(expandedGroup?.key === groupKey ? null : groupKey)
  }

  function regenerate() {
    setConfirming(false)
    generate.mutate(undefined, {
      onSuccess: () => {
        setExpandedGroupKey(undefined)
        setSelectedByGroup({})
      },
    })
  }

  function doConfirm() {
    if (!expanded) return
    confirm.mutate(
      { combinationId: expanded.combinationId },
      {
        onSuccess: () => navigate(`/sessions/${session.id}/confirmed`),
        onError: (err) => {
          if (isApiError(err) && (err.code === 'RECOMMENDATIONS_STALE' || err.code === 'SESSION_CLOSED')) refreshSession()
        },
      },
    )
  }

  const confirmError = confirm.isError
    ? isApiError(confirm.error) && confirm.error.code === 'RECOMMENDATIONS_STALE'
      ? 'These options are out of date. Update them before confirming.'
      : isApiError(confirm.error) && confirm.error.code === 'COMBINATION_NOT_FEASIBLE'
        ? "This option can't be confirmed any more. Pick another, or update the options."
        : confirm.error.message
    : null

  const excluded = Object.entries(set?.excludedCounts ?? {}).filter(([, n]) => n && n > 0) as [ExclusionReason, number][]

  return (
    <div className="results">
      <header className="results__head">
        <h2 className="results__name">{session.name}</h2>
        {set && (
          <p className="results__meta">
            Ranked {formatTime(set.generatedAt, session.timezone)} · {OBJECTIVE_LABELS[set.travelObjective]} ·{' '}
            {weightSplitText(set.attendanceWeightPercent)}
          </p>
        )}
      </header>

      {session.status === 'CONFIRMED' && (
        <p className="results__banner results__banner--ok">
          A plan has been confirmed. <Link to={`/sessions/${session.id}/confirmed`}>See the final plan</Link>
        </p>
      )}
      {session.status === 'CANCELLED' && (
        <p className="results__banner results__banner--muted">This session was cancelled.</p>
      )}
      {!session.activitySupported && (
        <p className="results__banner results__banner--muted">
          This historical session is read-only because its activity no longer has a verified venue catalogue. Existing results remain visible.
        </p>
      )}

      {/* UC-11.AC.1 */}
      {set && stale && active && mutable && (
        <div className="results__banner results__banner--warn" role="status">
          <p>Responses or details changed since these were ranked, so they may be out of date.</p>
          {isOrganiser && mutable ? (
            <button type="button" className="btn-primary" onClick={regenerate} disabled={generate.isPending}>
              {generate.isPending ? 'Updating…' : 'Update ranked options'}
            </button>
          ) : (
            <p>The organiser needs to update them.</p>
          )}
        </div>
      )}

      {set && set.isNearMatch && !stale && (
        <div className="results__banner results__banner--warn" role="status">
          <p>
            No time fits all {set.minimumAttendees} requested attendees. These are the best available alternatives, clearly
            showing who can and cannot attend.
          </p>
          {isOrganiser && mutable && (
            <p>
              To include everyone, ask the unavailable person to select one continuous {session.durationMinutes}-minute block,
              or edit the session duration/minimum below.
            </p>
          )}
        </div>
      )}

      {!set &&
        (isOrganiser && mutable ? (
          <StatusMessage
            title="Options haven't been ranked yet"
            action={
              <button type="button" className="btn-primary" onClick={regenerate} disabled={generate.isPending}>
                {generate.isPending ? 'Finding the best options…' : 'Rank options now'}
              </button>
            }
          >
            We'll find times that suit enough people and rank nearby venues by travel time.
          </StatusMessage>
        ) : (
          <StatusMessage title="No options yet">
            {session.activitySupported
              ? `${session.organiserName} hasn't ranked the options yet. Check back later.`
              : 'This historical session has no saved options and cannot generate new ones.'}
          </StatusMessage>
        ))}

      <GenerateError error={generate.error} onRetry={regenerate} />

      {set && isOrganiser && mutable && (
        <details className="results__adjust">
          <summary>Adjust ranking</summary>
          <div className="results__adjust-body">
            <ScoringControls session={session} />
          </div>
        </details>
      )}

      {set && combos.length === 0 && (
        <StatusMessage title="No options to show">
          Every possible time and venue was ruled out. Try lowering the minimum attendees or waiting for more responses.
        </StatusMessage>
      )}

      {groups.length > 0 && (
        <ol className="results__list" aria-label="Ranked options, best first">
          {groups.map((group, index) => {
            const selected = selectedOptionForGroup(
              group,
              selectedByGroup[group.key],
              session.confirmed?.combinationId,
            )
            const unavailable = selected.feasibilityStatus === 'DATA_UNAVAILABLE'
            const previousUnavailable = groups[index - 1]?.options[0].feasibilityStatus === 'DATA_UNAVAILABLE'
            return (
              <li key={group.key}>
                {unavailable && !previousUnavailable && (
                  // NFR-3: unavailable data is labelled, not hidden, and kept apart from normal ranking.
                  <p className="results__divider">
                    Missing some travel times, so these are listed last and can't be confirmed yet.
                  </p>
                )}
                <RankedOptionCard
                  options={group.options}
                  selectedCombinationId={selected.combinationId}
                  displayRank={group.displayRank}
                  requestedMinimum={set!.minimumAttendees}
                  timeZone={session.timezone}
                  expanded={expandedGroup?.key === group.key}
                  interactionDisabled={confirm.isPending}
                  onToggle={() => toggle(group.key)}
                  onSelectOption={(combinationId) =>
                    setSelectedByGroup((current) =>
                      chooseRecommendationTime(current, group.key, combinationId, confirm.isPending),
                    )
                  }
                  isConfirmed={session.confirmed?.combinationId === selected.combinationId}
                />
              </li>
            )
          })}
        </ol>
      )}

      {excluded.length > 0 && (
        <p className="results__excluded">
          Left out: {excluded.map(([reason, n]) => `${n} ${EXCLUSION_LABELS[reason]}`).join(' · ')}.
        </p>
      )}

      {set && mutable && combos.length > 0 && (
        <div className="results__actions">
          {!isOrganiser ? (
            <p className="results__hint">Only {session.organiserName} (the organiser) can confirm a plan.</p>
          ) : stale ? null : !expanded ? (
            <p className="results__hint">Tap an option to see its details and confirm it.</p>
          ) : expanded.feasibilityStatus !== 'FEASIBLE' ? (
            <p className="results__hint">
              This option is missing some travel times, so it can't be confirmed. Pick another, or update the options.
            </p>
          ) : confirming ? (
            <ConfirmPlanPanel
              option={expanded}
              requestedMinimum={set!.minimumAttendees}
              timeZone={session.timezone}
              busy={confirm.isPending}
              error={confirmError}
              onConfirm={doConfirm}
              onCancel={() => {
                setConfirming(false)
                confirm.reset()
              }}
            />
          ) : (
            <button type="button" className="btn-primary" onClick={() => setConfirming(true)}>
              {expandedGroup?.displayRank === 1
                ? 'Confirm top match at this time'
                : `Confirm option #${expandedGroup?.displayRank} at this time`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
