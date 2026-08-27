import { useState } from 'react'
import Dashboard from './views/Dashboard/Dashboard'
import ProfileForm from './components/ProfileForm/ProfileForm'
import AllJobs from './views/AllJobs/AllJobs'
import Tracking from './views/Tracking/Tracking'
import FetchRuns from './views/FetchRuns/FetchRuns'

type View = 'matches' | 'all-jobs' | 'tracking' | 'fetch-runs' | 'profile'

const TABS: { key: View; label: string }[] = [
  { key: 'matches', label: 'Matches' },
  { key: 'all-jobs', label: 'All Jobs' },
  { key: 'tracking', label: 'Tracking' },
  { key: 'fetch-runs', label: 'Fetch Runs' },
  { key: 'profile', label: 'Profile' },
]

export default function App() {
  const [view, setView] = useState<View>('matches')

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <nav className="bg-slate-800 border-b border-slate-700 px-6 py-2 flex gap-4 items-center shrink-0">
        <span className="text-slate-100 font-semibold text-sm mr-4">JobMatch AI</span>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setView(tab.key)}
            aria-current={view === tab.key ? 'page' : undefined}
            className={`text-sm px-3 py-1.5 rounded transition-colors ${
              view === tab.key
                ? 'bg-blue-500 text-white'
                : 'text-slate-400 hover:text-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {view === 'matches' && <Dashboard />}
      {view === 'all-jobs' && <AllJobs />}
      {view === 'tracking' && <Tracking />}
      {view === 'fetch-runs' && <FetchRuns />}
      {view === 'profile' && <ProfileForm />}
    </div>
  )
}
