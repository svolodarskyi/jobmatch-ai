import { useState } from 'react'
import Dashboard from './views/Dashboard/Dashboard'
import ProfileForm from './components/ProfileForm/ProfileForm'

type View = 'dashboard' | 'profile'

export default function App() {
  const [view, setView] = useState<View>('dashboard')

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <nav className="bg-slate-800 border-b border-slate-700 px-6 py-2 flex gap-4 items-center shrink-0">
        <span className="text-slate-100 font-semibold text-sm mr-4">JobMatch AI</span>
        <button
          onClick={() => setView('dashboard')}
          className={`text-sm px-3 py-1.5 rounded transition-colors ${
            view === 'dashboard'
              ? 'bg-blue-500 text-white'
              : 'text-slate-400 hover:text-slate-100'
          }`}
        >
          Dashboard
        </button>
        <button
          onClick={() => setView('profile')}
          className={`text-sm px-3 py-1.5 rounded transition-colors ${
            view === 'profile'
              ? 'bg-blue-500 text-white'
              : 'text-slate-400 hover:text-slate-100'
          }`}
        >
          Profile
        </button>
      </nav>
      {view === 'dashboard' ? <Dashboard /> : <ProfileForm />}
    </div>
  )
}
