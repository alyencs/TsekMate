import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { Subject } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { ActivitiesTable } from '../components/activities/ActivitiesTable'
import { ErrorState, Loading } from '../components/ui/States'

export default function Activities() {
  const [params] = useSearchParams()
  const subject = (params.get('subject') as Subject | null) ?? 'all'
  const [q, setQ] = useState('')
  const acts = useAsync(() => api.activities(), [])
  return (
    <AppShell active="activities" topbar={<TopBar title="Activities" search={{ placeholder: 'Search activities...', value: q, onChange: setQ }} />}>
      {acts.error ? (
        <ErrorState message={acts.error} onRetry={acts.reload} />
      ) : !acts.data ? (
        <Loading />
      ) : (
        <ActivitiesTable key={subject} activities={acts.data} query={q} initialSubject={subject} title="All activities" />
      )}
    </AppShell>
  )
}
