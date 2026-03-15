import { A } from '../theme'

export const PILLAR_COLORS: Record<string, string> = {
  education: A.indigo,
  inspiration: A.violet,
  promotion: A.coral,
  behind_the_scenes: A.emerald,
  user_generated: A.amber,
}

export const STATUS_COLORS: Record<string, string> = {
  approved: A.emerald,
  complete: A.indigo,
  generating: A.amber,
  failed: A.coral,
  draft: A.textMuted,
}

export const STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  complete: 'Ready',
  generating: 'Generating',
  failed: 'Failed',
  draft: 'Draft',
}

/** STATUS_LABELS variant used in PostCard (includes emoji prefixes). */
export const STATUS_LABELS_DECORATED: Record<string, string> = {
  approved: '\u2713 Approved',
  complete: 'Ready',
  generating: '\u27F3 Generating',
  failed: '\u2717 Failed',
  draft: 'Draft',
}
