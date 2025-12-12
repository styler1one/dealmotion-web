'use client'

import { useState, useEffect } from 'react'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'

const tabs = [
  { key: 'research', label: 'Research', icon: 'search' },
  { key: 'preparation', label: 'Preparation', icon: 'fileText' },
  { key: 'recording', label: 'Recording', icon: 'mic' },
  { key: 'analysis', label: 'Analysis', icon: 'sparkles' },
] as const

type TabKey = typeof tabs[number]['key']

export function HeroShowcase() {
  const [activeTab, setActiveTab] = useState<TabKey>('research')
  const [isAutoPlaying, setIsAutoPlaying] = useState(true)

  // Auto-rotate tabs
  useEffect(() => {
    if (!isAutoPlaying) return
    
    const interval = setInterval(() => {
      setActiveTab((current) => {
        const currentIndex = tabs.findIndex(t => t.key === current)
        const nextIndex = (currentIndex + 1) % tabs.length
        return tabs[nextIndex].key
      })
    }, 5000)

    return () => clearInterval(interval)
  }, [isAutoPlaying])

  const getIcon = (iconName: string) => {
    const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
      search: Icons.search,
      fileText: Icons.fileText,
      mic: Icons.mic,
      sparkles: Icons.sparkles,
    }
    return iconMap[iconName] || Icons.circle
  }

  return (
    <div 
      className="rounded-2xl border dark:border-slate-800 shadow-2xl overflow-hidden bg-white dark:bg-slate-900"
      onMouseEnter={() => setIsAutoPlaying(false)}
      onMouseLeave={() => setIsAutoPlaying(true)}
    >
      {/* Browser Chrome */}
      <div className="h-10 bg-slate-100 dark:bg-slate-800 border-b dark:border-slate-700 flex items-center px-4 gap-2">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-400" />
          <div className="w-3 h-3 rounded-full bg-yellow-400" />
          <div className="w-3 h-3 rounded-full bg-green-400" />
        </div>
        <div className="flex-1 flex justify-center">
          <div className="px-4 py-1 bg-white dark:bg-slate-700 rounded-md text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <Icons.globe className="h-3 w-3" />
            dealmotion.ai
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        {tabs.map((tab) => {
          const Icon = getIcon(tab.icon)
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key)
                setIsAutoPlaying(false)
              }}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-3 px-4 text-sm font-medium transition-all",
                isActive 
                  ? "text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-white dark:bg-slate-900" 
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 min-h-[360px]">
        {activeTab === 'research' && <ResearchMockup />}
        {activeTab === 'preparation' && <PreparationMockup />}
        {activeTab === 'recording' && <RecordingMockup />}
        {activeTab === 'analysis' && <AnalysisMockup />}
      </div>

      {/* Progress Dots */}
      <div className="flex justify-center gap-2 py-3 bg-white dark:bg-slate-900 border-t dark:border-slate-800">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key)
              setIsAutoPlaying(false)
            }}
            className={cn(
              "w-2 h-2 rounded-full transition-all",
              activeTab === tab.key
                ? "w-6 bg-blue-600"
                : "bg-slate-300 dark:bg-slate-600 hover:bg-slate-400"
            )}
          />
        ))}
      </div>
    </div>
  )
}

// Research Brief Mockup
function ResearchMockup() {
  return (
    <div className="p-6 space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
            <Icons.building className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-white">TechCorp Industries</h3>
            <p className="text-xs text-slate-500">Research completed • 2 min ago</p>
          </div>
        </div>
        <span className="px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-medium">
          Complete
        </span>
      </div>

      {/* Quick Facts */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border dark:border-slate-700">
          <p className="text-xs text-slate-500 mb-1">Industry</p>
          <p className="text-sm font-medium text-slate-900 dark:text-white">SaaS / Tech</p>
        </div>
        <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border dark:border-slate-700">
          <p className="text-xs text-slate-500 mb-1">Employees</p>
          <p className="text-sm font-medium text-slate-900 dark:text-white">250-500</p>
        </div>
        <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border dark:border-slate-700">
          <p className="text-xs text-slate-500 mb-1">Revenue</p>
          <p className="text-sm font-medium text-slate-900 dark:text-white">€50M+</p>
        </div>
      </div>

      {/* Key Insights */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
          <Icons.lightbulb className="h-4 w-4 text-amber-500" />
          Key Insights
        </h4>
        <ul className="space-y-2">
          <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
            <Icons.check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
            Recently raised Series B funding (€25M)
          </li>
          <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
            <Icons.check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
            Expanding to European markets in Q1
          </li>
          <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
            <Icons.check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
            Pain point: scaling sales operations
          </li>
        </ul>
      </div>

      {/* Challenges */}
      <div className="p-4 rounded-xl bg-orange-50 dark:bg-orange-900/20 border border-orange-100 dark:border-orange-900/30">
        <h4 className="text-sm font-semibold text-orange-800 dark:text-orange-300 mb-2 flex items-center gap-2">
          <Icons.target className="h-4 w-4" />
          Challenges You Can Solve
        </h4>
        <p className="text-sm text-orange-700 dark:text-orange-400">
          Need to onboard 15 new sales reps while maintaining quality...
        </p>
      </div>
    </div>
  )
}

// Meeting Preparation Mockup
function PreparationMockup() {
  return (
    <div className="p-6 space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <Icons.fileText className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-white">Meeting Brief</h3>
            <p className="text-xs text-slate-500">TechCorp • Sarah Johnson (CFO)</p>
          </div>
        </div>
        <span className="px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-medium">
          Today 2:00 PM
        </span>
      </div>

      {/* Opening Line */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-100 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">💬 Opening Line</h4>
        <p className="text-sm text-blue-700 dark:text-blue-400 italic">
          "Sarah, I saw TechCorp just announced the European expansion. Congratulations! I'd love to hear how you're thinking about scaling the sales team..."
        </p>
      </div>

      {/* Talking Points */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">📋 Key Talking Points</h4>
        <ul className="space-y-2">
          <li className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <div className="w-5 h-5 rounded bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-xs text-green-600">1</div>
            Sales team scaling challenges
          </li>
          <li className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <div className="w-5 h-5 rounded bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-xs text-green-600">2</div>
            European market requirements
          </li>
          <li className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <div className="w-5 h-5 rounded bg-green-100 dark:bg-green-900/30 flex items-center justify-center text-xs text-green-600">3</div>
            Current onboarding process
          </li>
        </ul>
      </div>

      {/* SPIN Questions */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">🎯 Discovery Questions</h4>
        <div className="space-y-2">
          <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 text-sm text-slate-600 dark:text-slate-300">
            <span className="text-purple-600 dark:text-purple-400 font-medium">S:</span> How are you currently preparing reps for customer meetings?
          </div>
          <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 text-sm text-slate-600 dark:text-slate-300">
            <span className="text-orange-600 dark:text-orange-400 font-medium">P:</span> What happens when a rep walks in unprepared?
          </div>
        </div>
      </div>
    </div>
  )
}

// AI Notetaker Recording Mockup
function RecordingMockup() {
  return (
    <div className="p-6 space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center animate-pulse">
            <Icons.mic className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-white">AI Notetaker Active</h3>
            <p className="text-xs text-slate-500">Recording in progress...</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-sm font-mono text-red-600 dark:text-red-400">23:45</span>
        </div>
      </div>

      {/* Meeting Info */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="font-semibold text-slate-900 dark:text-white">Discovery Call</h4>
            <p className="text-sm text-slate-500">TechCorp Industries</p>
          </div>
          <div className="flex items-center gap-1">
            <Icons.sparkles className="h-4 w-4 text-violet-500" />
            <span className="text-xs text-violet-600 dark:text-violet-400 font-medium">DealMotion AI Notes</span>
          </div>
        </div>

        {/* Participants */}
        <div className="flex items-center gap-2 mb-4">
          <div className="flex -space-x-2">
            <div className="w-8 h-8 rounded-full bg-blue-500 border-2 border-white dark:border-slate-800 flex items-center justify-center text-white text-xs font-medium">SJ</div>
            <div className="w-8 h-8 rounded-full bg-green-500 border-2 border-white dark:border-slate-800 flex items-center justify-center text-white text-xs font-medium">MC</div>
            <div className="w-8 h-8 rounded-full bg-purple-500 border-2 border-white dark:border-slate-800 flex items-center justify-center text-white text-xs font-medium">You</div>
          </div>
          <span className="text-sm text-slate-500">3 participants</span>
        </div>

        {/* Platform */}
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Icons.globe className="h-4 w-4" />
          Microsoft Teams
        </div>
      </div>

      {/* Live Indicators */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800">
          <div className="flex items-center gap-2 mb-2">
            <Icons.check className="h-4 w-4 text-green-600" />
            <span className="text-sm font-medium text-green-800 dark:text-green-300">Transcribing</span>
          </div>
          <p className="text-xs text-green-600 dark:text-green-400">Live transcription active</p>
        </div>
        <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800">
          <div className="flex items-center gap-2 mb-2">
            <Icons.sparkles className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800 dark:text-blue-300">AI Ready</span>
          </div>
          <p className="text-xs text-blue-600 dark:text-blue-400">7 outputs when done</p>
        </div>
      </div>

      {/* Status Timeline */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
              <Icons.check className="h-3 w-3 text-white" />
            </div>
            <span className="text-xs text-slate-500">Joined</span>
          </div>
          <div className="flex-1 h-0.5 bg-green-500" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center animate-pulse">
              <Icons.mic className="h-3 w-3 text-white" />
            </div>
            <span className="text-xs text-slate-500">Recording</span>
          </div>
          <div className="flex-1 h-0.5 bg-slate-200 dark:bg-slate-700" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
              <Icons.sparkles className="h-3 w-3 text-slate-400" />
            </div>
            <span className="text-xs text-slate-400">Analysis</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Meeting Analysis Mockup (7 Outputs)
function AnalysisMockup() {
  const outputs = [
    { icon: 'fileText', label: 'Summary', status: 'done', color: 'blue' },
    { icon: 'mail', label: 'Customer Report', status: 'done', color: 'green' },
    { icon: 'users', label: 'Share Email', status: 'done', color: 'purple' },
    { icon: 'barChart', label: 'Commercial Analysis', status: 'done', color: 'orange' },
    { icon: 'sparkles', label: 'Sales Coaching', status: 'done', color: 'pink' },
    { icon: 'check', label: 'Action Items', status: 'done', color: 'emerald' },
    { icon: 'building', label: 'CRM Update', status: 'done', color: 'cyan' },
  ]

  const getIcon = (name: string) => {
    const map: Record<string, React.ComponentType<{ className?: string }>> = {
      fileText: Icons.fileText,
      mail: Icons.mail,
      users: Icons.users,
      barChart: Icons.barChart,
      sparkles: Icons.sparkles,
      check: Icons.checkCircle,
      building: Icons.building,
    }
    return map[name] || Icons.circle
  }

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    green: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    purple: 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
    orange: 'bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400',
    pink: 'bg-pink-100 dark:bg-pink-900/30 text-pink-600 dark:text-pink-400',
    emerald: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400',
    cyan: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400',
  }

  return (
    <div className="p-6 space-y-4 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Icons.sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-white">Meeting Analysis</h3>
            <p className="text-xs text-slate-500">TechCorp Discovery Call • 24 min</p>
          </div>
        </div>
        <span className="px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-medium flex items-center gap-1">
          <Icons.check className="h-3 w-3" />
          7/7 Ready
        </span>
      </div>

      {/* Outputs Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {outputs.slice(0, 4).map((output) => {
          const Icon = getIcon(output.icon)
          return (
            <div 
              key={output.label}
              className="p-3 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700 hover:shadow-md transition-shadow cursor-pointer"
            >
              <div className={`w-8 h-8 rounded-lg ${colorMap[output.color]} flex items-center justify-center mb-2`}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="text-xs font-medium text-slate-900 dark:text-white">{output.label}</p>
              <p className="text-xs text-green-600 dark:text-green-400">Ready</p>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {outputs.slice(4).map((output) => {
          const Icon = getIcon(output.icon)
          return (
            <div 
              key={output.label}
              className="p-3 rounded-xl bg-white dark:bg-slate-800 border dark:border-slate-700 hover:shadow-md transition-shadow cursor-pointer"
            >
              <div className={`w-8 h-8 rounded-lg ${colorMap[output.color]} flex items-center justify-center mb-2`}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="text-xs font-medium text-slate-900 dark:text-white">{output.label}</p>
              <p className="text-xs text-green-600 dark:text-green-400">Ready</p>
            </div>
          )
        })}
      </div>

      {/* Quick Preview */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-100 dark:border-blue-800">
        <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2 flex items-center gap-2">
          <Icons.fileText className="h-4 w-4" />
          Summary Preview
        </h4>
        <p className="text-sm text-blue-700 dark:text-blue-400">
          Productive discovery call with Sarah Johnson (CFO). Key pain point: scaling sales team for European expansion. 
          Strong buying signals detected. Next step: product demo with sales leadership...
        </p>
      </div>
    </div>
  )
}

