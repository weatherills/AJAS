export type OnboardingStep = {
  id: string
  label: string
  done: boolean
  href: string
}

export function onboardingSteps(input: {
  emailConnected: boolean
  sourceEnabled: boolean
  thresholdSet: boolean
  reviewed: boolean
}): OnboardingStep[] {
  return [
    {
      id: 'email',
      label: 'Connect Microsoft 365 (or keep the demo mailbox)',
      done: input.emailConnected,
      href: '#/settings',
    },
    {
      id: 'sources',
      label: 'Add a Greenhouse or Lever board',
      done: input.sourceEnabled,
      href: '#/settings',
    },
    {
      id: 'threshold',
      label: 'Confirm your match threshold',
      done: input.thresholdSet,
      href: '#/settings',
    },
    {
      id: 'review',
      label: 'Review a match',
      done: input.reviewed,
      href: '#/review',
    },
  ]
}
