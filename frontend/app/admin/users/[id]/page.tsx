'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { adminApi } from '@/lib/admin-api'
import { HealthScoreCard } from '@/components/admin/stats-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { AdminUserDetail, ActivityItem, UserBillingResponse, UserErrorsResponse, HealthBreakdown } from '@/types/admin'

// Simple toast notification component
function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div className={cn(
      'fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 z-50 animate-in slide-in-from-bottom-5',
      type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
    )}>
      {type === 'success' ? <Icons.checkCircle className="h-5 w-5" /> : <Icons.xCircle className="h-5 w-5" />}
      {message}
    </div>
  )
}

export default function AdminUserDetailPage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.id as string

  const [user, setUser] = useState<AdminUserDetail | null>(null)
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [billingData, setBillingData] = useState<UserBillingResponse | null>(null)
  const [errorsData, setErrorsData] = useState<UserErrorsResponse | null>(null)
  const [healthBreakdown, setHealthBreakdown] = useState<HealthBreakdown | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  
  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  
  // Action dialogs
  const [showResetDialog, setShowResetDialog] = useState(false)
  const [showAddFlowsDialog, setShowAddFlowsDialog] = useState(false)
  const [showExtendTrialDialog, setShowExtendTrialDialog] = useState(false)
  const [showNoteDialog, setShowNoteDialog] = useState(false)
  const [showEditNoteDialog, setShowEditNoteDialog] = useState(false)
  const [showDeleteNoteDialog, setShowDeleteNoteDialog] = useState(false)
  
  // Action form state
  const [actionReason, setActionReason] = useState('')
  const [flowsToAdd, setFlowsToAdd] = useState(5)
  const [daysToExtend, setDaysToExtend] = useState(7)
  const [noteContent, setNoteContent] = useState('')
  const [notePinned, setNotePinned] = useState(false)
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
  }

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [userData, activityData, healthData] = await Promise.all([
          adminApi.getUser(userId),
          adminApi.getUserActivity(userId, 20),
          adminApi.getUserHealthBreakdown(userId).catch(() => null),
        ])
        setUser(userData)
        setActivities(activityData.activities)
        setHealthBreakdown(healthData)
      } catch (err) {
        console.error('Failed to fetch user:', err)
        showToast('Failed to load user data', 'error')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [userId])

  // Lazy load billing and errors data when tab is selected
  useEffect(() => {
    if (activeTab === 'billing' && !billingData) {
      adminApi.getUserBilling(userId).then(setBillingData).catch(console.error)
    }
    if (activeTab === 'errors' && !errorsData) {
      adminApi.getUserErrors(userId).then(setErrorsData).catch(console.error)
    }
  }, [activeTab, userId, billingData, errorsData])

  const refreshUserData = async () => {
    try {
      const userData = await adminApi.getUser(userId)
      setUser(userData)
    } catch (err) {
      console.error('Failed to refresh user data:', err)
    }
  }

  const handleResetFlows = async () => {
    if (!actionReason.trim()) return
    setActionLoading(true)
    try {
      await adminApi.resetFlows(userId, { reason: actionReason })
      await refreshUserData()
      setShowResetDialog(false)
      setActionReason('')
      showToast('Monthly flows reset successfully', 'success')
    } catch (err) {
      console.error('Failed to reset flows:', err)
      showToast('Failed to reset flows', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddFlows = async () => {
    if (!actionReason.trim() || flowsToAdd < 1) return
    setActionLoading(true)
    try {
      await adminApi.addFlows(userId, { flows: flowsToAdd, reason: actionReason })
      await refreshUserData()
      setShowAddFlowsDialog(false)
      setActionReason('')
      setFlowsToAdd(5)
      showToast(`Added ${flowsToAdd} bonus flows`, 'success')
    } catch (err) {
      console.error('Failed to add flows:', err)
      showToast('Failed to add flows', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleExtendTrial = async () => {
    if (!actionReason.trim() || daysToExtend < 1) return
    setActionLoading(true)
    try {
      await adminApi.extendTrial(userId, { days: daysToExtend, reason: actionReason })
      await refreshUserData()
      setShowExtendTrialDialog(false)
      setActionReason('')
      setDaysToExtend(7)
      showToast(`Trial extended by ${daysToExtend} days`, 'success')
    } catch (err) {
      console.error('Failed to extend trial:', err)
      showToast('Failed to extend trial', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddNote = async () => {
    if (!noteContent.trim()) return
    setActionLoading(true)
    try {
      await adminApi.createNote({
        targetType: 'user',
        targetId: userId,
        content: noteContent,
        isPinned: notePinned,
      })
      await refreshUserData()
      setShowNoteDialog(false)
      setNoteContent('')
      setNotePinned(false)
      showToast('Note added successfully', 'success')
    } catch (err) {
      console.error('Failed to add note:', err)
      showToast('Failed to add note', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleEditNote = async () => {
    if (!noteContent.trim() || !editingNoteId) return
    setActionLoading(true)
    try {
      await adminApi.updateNote(editingNoteId, {
        content: noteContent,
        isPinned: notePinned,
      })
      await refreshUserData()
      setShowEditNoteDialog(false)
      setNoteContent('')
      setNotePinned(false)
      setEditingNoteId(null)
      showToast('Note updated successfully', 'success')
    } catch (err) {
      console.error('Failed to update note:', err)
      showToast('Failed to update note', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteNote = async () => {
    if (!editingNoteId) return
    setActionLoading(true)
    try {
      await adminApi.deleteNote(editingNoteId)
      await refreshUserData()
      setShowDeleteNoteDialog(false)
      setEditingNoteId(null)
      showToast('Note deleted successfully', 'success')
    } catch (err) {
      console.error('Failed to delete note:', err)
      showToast('Failed to delete note', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleTogglePin = async (noteId: string, currentPinned: boolean) => {
    try {
      await adminApi.updateNote(noteId, { isPinned: !currentPinned })
      await refreshUserData()
      showToast(currentPinned ? 'Note unpinned' : 'Note pinned', 'success')
    } catch (err) {
      console.error('Failed to toggle pin:', err)
      showToast('Failed to update note', 'error')
    }
  }

  const openEditNoteDialog = (note: { id: string; content: string; isPinned: boolean }) => {
    setEditingNoteId(note.id)
    setNoteContent(note.content)
    setNotePinned(note.isPinned)
    setShowEditNoteDialog(true)
  }

  const openDeleteNoteDialog = (noteId: string) => {
    setEditingNoteId(noteId)
    setShowDeleteNoteDialog(true)
  }

  const handleExport = async () => {
    try {
      const data = await adminApi.exportUser(userId)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `user-${userId}-export.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      showToast('User data exported', 'success')
    } catch (err) {
      console.error('Failed to export:', err)
      showToast('Failed to export user data', 'error')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Icons.spinner className="h-8 w-8 animate-spin text-teal-500" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Icons.userX className="h-12 w-12 text-slate-400 mb-4" />
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
          User Not Found
        </h2>
        <Button onClick={() => router.push('/admin/users')}>
          Back to Users
        </Button>
      </div>
    )
  }

  const tabs = [
    { key: 'overview', label: 'Overview', icon: Icons.user },
    { key: 'activity', label: 'Activity', icon: Icons.activity },
    { key: 'flow_packs', label: 'Flow Packs', icon: Icons.package },
    { key: 'billing', label: 'Billing', icon: Icons.creditCard },
    { key: 'errors', label: 'Errors', icon: Icons.alertTriangle, badge: user.errorCount30d > 0 ? user.errorCount30d : undefined },
    { key: 'notes', label: 'Notes', icon: Icons.fileText, badge: user.adminNotes.length > 0 ? user.adminNotes.length : undefined },
  ]

  const getInitials = (name?: string, email?: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    }
    return email?.slice(0, 2).toUpperCase() || '?'
  }

  const formatCurrency = (cents: number, currency = 'eur') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(cents / 100)
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <Toast 
          message={toast.message} 
          type={toast.type} 
          onClose={() => setToast(null)} 
        />
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div className={cn(
            'w-16 h-16 rounded-full flex items-center justify-center text-xl font-semibold',
            user.plan === 'unlimited_solo' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
            user.plan === 'pro_solo' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
            'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
          )}>
            {getInitials(user.fullName, user.email)}
          </div>
          <div>
            <Button 
              variant="ghost" 
              className="mb-1 -ml-3 h-auto p-1"
              onClick={() => router.push('/admin/users')}
            >
              <Icons.arrowLeft className="h-4 w-4 mr-1" />
              Back to Users
            </Button>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              {user.fullName || user.email}
            </h1>
            <p className="text-slate-500">{user.email}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Icons.download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-slate-500">Plan</div>
            <div className="text-lg font-semibold capitalize">{user.plan.replace('_', ' ')}</div>
            {user.subscriptionStatus === 'trialing' && user.trialEndsAt && (
              <div className="text-xs text-amber-500 mt-1">
                Trial ends {new Date(user.trialEndsAt).toLocaleDateString()}
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-slate-500">Flows Used</div>
            <div className="text-lg font-semibold">
              {user.flowUsage.used}
              {user.flowUsage.limit !== -1 ? `/${user.flowUsage.limit}` : ' (∞)'}
              {user.flowUsage.packBalance > 0 && (
                <span className="text-sm text-purple-500 ml-1">+{user.flowUsage.packBalance}</span>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-slate-500">Total Activity</div>
            <div className="text-lg font-semibold">
              {user.totalResearches + user.totalPreps + user.totalFollowups}
            </div>
            <div className="text-xs text-slate-400">
              {user.totalResearches}R / {user.totalPreps}P / {user.totalFollowups}F
            </div>
          </CardContent>
        </Card>
        <HealthScoreCard 
          score={user.healthScore} 
          status={user.healthStatus}
          className="md:row-span-1"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <nav className="flex gap-4">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
                  activeTab === tab.key
                    ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                {tab.badge !== undefined && tab.badge > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-slate-200 dark:bg-slate-700 rounded-full">
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {activeTab === 'overview' && (
            <Card>
              <CardHeader>
                <CardTitle>User Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-slate-500">Email</div>
                    <div className="font-medium">{user.email}</div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-500">Organization</div>
                    <div className="font-medium">{user.organizationName || '-'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-500">Subscription Status</div>
                    <div className="font-medium capitalize">{user.subscriptionStatus || 'None'}</div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-500">Profile Completeness</div>
                    <div className="font-medium">{user.profileCompleteness}%</div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-500">Member Since</div>
                    <div className="font-medium">
                      {new Date(user.createdAt).toLocaleDateString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-500">Last Active</div>
                    <div className="font-medium">
                      {user.lastActive 
                        ? new Date(user.lastActive).toLocaleDateString()
                        : 'Never'
                      }
                    </div>
                  </div>
                  {user.trialEndsAt && (
                    <div>
                      <div className="text-sm text-slate-500">Trial Ends</div>
                      <div className="font-medium">
                        {new Date(user.trialEndsAt).toLocaleDateString()}
                      </div>
                    </div>
                  )}
                  <div>
                    <div className="text-sm text-slate-500">Errors (30d)</div>
                    <div className={cn(
                      'font-medium',
                      user.errorCount30d > 5 ? 'text-red-500' : 
                      user.errorCount30d > 2 ? 'text-amber-500' : 
                      'text-green-500'
                    )}>
                      {user.errorCount30d}
                    </div>
                  </div>
                </div>

                {/* Usage Stats */}
                <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
                  <h4 className="font-medium mb-3">Usage Statistics</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <div className="text-2xl font-bold text-blue-500">{user.totalResearches}</div>
                      <div className="text-xs text-slate-500">Researches</div>
                    </div>
                    <div className="text-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <div className="text-2xl font-bold text-green-500">{user.totalPreps}</div>
                      <div className="text-xs text-slate-500">Preparations</div>
                    </div>
                    <div className="text-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <div className="text-2xl font-bold text-orange-500">{user.totalFollowups}</div>
                      <div className="text-xs text-slate-500">Follow-ups</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === 'activity' && (
            <Card>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                {activities.length > 0 ? (
                  <div className="space-y-3">
                    {activities.map((activity) => (
                      <div key={activity.id} className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className={cn(
                          'p-2 rounded-full',
                          activity.type === 'research' ? 'bg-blue-100 text-blue-500 dark:bg-blue-900/30' :
                          activity.type === 'preparation' ? 'bg-green-100 text-green-500 dark:bg-green-900/30' :
                          'bg-orange-100 text-orange-500 dark:bg-orange-900/30'
                        )}>
                          {activity.type === 'research' ? <Icons.search className="h-4 w-4" /> :
                           activity.type === 'preparation' ? <Icons.fileText className="h-4 w-4" /> :
                           <Icons.mail className="h-4 w-4" />}
                        </div>
                        <div className="flex-1">
                          <div className="font-medium text-sm">{activity.description}</div>
                          <div className="text-xs text-slate-500">
                            {new Date(activity.createdAt).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <Icons.activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    No recent activity
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTab === 'flow_packs' && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Flow Packs</CardTitle>
                <Button size="sm" onClick={() => setShowAddFlowsDialog(true)}>
                  <Icons.plus className="h-4 w-4 mr-1" />
                  Add Pack
                </Button>
              </CardHeader>
              <CardContent>
                {user.flowPacks.length > 0 ? (
                  <div className="space-y-3">
                    {user.flowPacks.map((pack) => (
                      <div key={pack.id} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div>
                          <div className="font-medium">
                            {pack.flowsRemaining} / {pack.flowsPurchased} flows remaining
                          </div>
                          <div className="text-xs text-slate-500">
                            Purchased {new Date(pack.purchasedAt).toLocaleDateString()}
                          </div>
                        </div>
                        <span className={cn(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          pack.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                          pack.status === 'depleted' ? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400' :
                          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        )}>
                          {pack.status}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <Icons.package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    No flow packs
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTab === 'notes' && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Admin Notes</CardTitle>
                <Button size="sm" onClick={() => setShowNoteDialog(true)}>
                  <Icons.plus className="h-4 w-4 mr-1" />
                  Add Note
                </Button>
              </CardHeader>
              <CardContent>
                {user.adminNotes.length > 0 ? (
                  <div className="space-y-3">
                    {user.adminNotes.map((note) => (
                      <div key={note.id} className={cn(
                        'p-3 rounded-lg border group',
                        note.isPinned ? 'border-teal-200 bg-teal-50 dark:bg-teal-900/20 dark:border-teal-800' : 
                        'border-slate-100 bg-slate-50 dark:bg-slate-800 dark:border-slate-700'
                      )}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            {note.isPinned && (
                              <div className="flex items-center gap-1 text-xs text-teal-600 dark:text-teal-400 mb-2">
                                <Icons.pin className="h-3 w-3" />
                                Pinned
                              </div>
                            )}
                            <div className="text-sm whitespace-pre-wrap">{note.content}</div>
                            <div className="text-xs text-slate-500 mt-2">
                              By {note.adminName} • {new Date(note.createdAt).toLocaleString()}
                            </div>
                          </div>
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleTogglePin(note.id, note.isPinned)}
                              title={note.isPinned ? 'Unpin' : 'Pin'}
                            >
                              <Icons.pin className={cn('h-4 w-4', note.isPinned && 'text-teal-500')} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditNoteDialog(note)}
                              title="Edit"
                            >
                              <Icons.edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openDeleteNoteDialog(note.id)}
                              title="Delete"
                              className="text-red-500 hover:text-red-600"
                            >
                              <Icons.trash className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">
                    <Icons.fileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    No notes yet
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTab === 'billing' && (
            <Card>
              <CardHeader>
                <CardTitle>Billing & Payments</CardTitle>
              </CardHeader>
              <CardContent>
                {!billingData ? (
                  <div className="flex items-center justify-center py-8">
                    <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Subscription Summary */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Plan</div>
                        <div className="font-semibold capitalize">{billingData.plan.replace('_', ' ')}</div>
                      </div>
                      <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Status</div>
                        <div className={cn(
                          'font-semibold capitalize',
                          billingData.subscriptionStatus === 'active' ? 'text-green-500' :
                          billingData.subscriptionStatus === 'past_due' ? 'text-red-500' :
                          'text-slate-500'
                        )}>
                          {billingData.subscriptionStatus || 'None'}
                        </div>
                      </div>
                      <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Total Paid</div>
                        <div className="font-semibold text-green-500">{formatCurrency(billingData.totalPaidCents)}</div>
                      </div>
                      <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Payments</div>
                        <div className="font-semibold">{billingData.totalPayments}</div>
                      </div>
                    </div>

                    {billingData.currentPeriodEnd && (
                      <div className="text-sm text-slate-500">
                        Current period ends: {new Date(billingData.currentPeriodEnd).toLocaleDateString()}
                        {billingData.cancelAtPeriodEnd && (
                          <span className="ml-2 text-amber-500">(Cancelling at period end)</span>
                        )}
                      </div>
                    )}

                    {/* Payment History */}
                    <div>
                      <h4 className="font-medium mb-3">Payment History</h4>
                      {billingData.payments.length > 0 ? (
                        <div className="space-y-2">
                          {billingData.payments.map((payment) => (
                            <div key={payment.id} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                              <div className="flex items-center gap-3">
                                <div className={cn(
                                  'p-2 rounded-full',
                                  payment.status === 'paid' ? 'bg-green-100 text-green-500 dark:bg-green-900/30' :
                                  payment.status === 'failed' ? 'bg-red-100 text-red-500 dark:bg-red-900/30' :
                                  'bg-slate-100 text-slate-500 dark:bg-slate-700'
                                )}>
                                  {payment.status === 'paid' ? <Icons.checkCircle className="h-4 w-4" /> :
                                   payment.status === 'failed' ? <Icons.xCircle className="h-4 w-4" /> :
                                   <Icons.clock className="h-4 w-4" />}
                                </div>
                                <div>
                                  <div className="font-medium">{formatCurrency(payment.amountCents, payment.currency)}</div>
                                  <div className="text-xs text-slate-500">
                                    {payment.invoiceNumber || 'Invoice'} • {new Date(payment.createdAt).toLocaleDateString()}
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={cn(
                                  'px-2 py-0.5 rounded-full text-xs font-medium capitalize',
                                  payment.status === 'paid' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                  payment.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                                  'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                                )}>
                                  {payment.status}
                                </span>
                                {payment.invoicePdfUrl && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => window.open(payment.invoicePdfUrl, '_blank')}
                                  >
                                    <Icons.download className="h-4 w-4" />
                                  </Button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-slate-500">
                          <Icons.creditCard className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          No payment history
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTab === 'errors' && (
            <Card>
              <CardHeader>
                <CardTitle>Errors & Failed Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                {!errorsData ? (
                  <div className="flex items-center justify-center py-8">
                    <Icons.spinner className="h-6 w-6 animate-spin text-teal-500" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Error Rate Summary */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Error Rate (7 days)</div>
                        <div className={cn(
                          'text-2xl font-bold',
                          errorsData.errorRate7d > 20 ? 'text-red-500' :
                          errorsData.errorRate7d > 10 ? 'text-amber-500' :
                          'text-green-500'
                        )}>
                          {errorsData.errorRate7d}%
                        </div>
                      </div>
                      <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <div className="text-sm text-slate-500">Error Rate (30 days)</div>
                        <div className={cn(
                          'text-2xl font-bold',
                          errorsData.errorRate30d > 20 ? 'text-red-500' :
                          errorsData.errorRate30d > 10 ? 'text-amber-500' :
                          'text-green-500'
                        )}>
                          {errorsData.errorRate30d}%
                        </div>
                      </div>
                    </div>

                    {/* Error List */}
                    <div>
                      <h4 className="font-medium mb-3">Recent Errors ({errorsData.total})</h4>
                      {errorsData.errors.length > 0 ? (
                        <div className="space-y-2">
                          {errorsData.errors.map((error) => (
                            <div key={error.id} className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/50 rounded-lg">
                              <div className="flex items-start gap-3">
                                <div className="p-1.5 bg-red-100 dark:bg-red-900/30 rounded">
                                  <Icons.alertTriangle className="h-4 w-4 text-red-500" />
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-medium text-sm">{error.title}</span>
                                    <span className="px-1.5 py-0.5 text-xs bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded capitalize">
                                      {error.type.replace('_', ' ')}
                                    </span>
                                  </div>
                                  {error.errorMessage && (
                                    <div className="text-sm text-red-600 dark:text-red-400 font-mono bg-red-100/50 dark:bg-red-900/20 p-2 rounded mt-1">
                                      {error.errorMessage}
                                    </div>
                                  )}
                                  <div className="text-xs text-slate-500 mt-2">
                                    {new Date(error.createdAt).toLocaleString()}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-slate-500">
                          <Icons.checkCircle className="h-8 w-8 mx-auto mb-2 opacity-50 text-green-500" />
                          No errors found
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Actions Sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button 
                variant="outline" 
                className="w-full justify-start"
                onClick={() => setShowResetDialog(true)}
              >
                <Icons.refresh className="h-4 w-4 mr-2" />
                Reset Monthly Flows
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start"
                onClick={() => setShowAddFlowsDialog(true)}
              >
                <Icons.plus className="h-4 w-4 mr-2" />
                Add Bonus Flows
              </Button>
              {(user.subscriptionStatus === 'trialing' || user.plan === 'free') && (
                <Button 
                  variant="outline" 
                  className="w-full justify-start"
                  onClick={() => setShowExtendTrialDialog(true)}
                >
                  <Icons.calendar className="h-4 w-4 mr-2" />
                  Extend Trial
                </Button>
              )}
              <Button 
                variant="outline" 
                className="w-full justify-start"
                onClick={() => setShowNoteDialog(true)}
              >
                <Icons.fileText className="h-4 w-4 mr-2" />
                Add Note
              </Button>
              {user.stripeCustomerId && (
                <Button 
                  variant="outline" 
                  className="w-full justify-start"
                  onClick={() => window.open(`https://dashboard.stripe.com/customers/${user.stripeCustomerId}`, '_blank')}
                >
                  <Icons.externalLink className="h-4 w-4 mr-2" />
                  View in Stripe
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Health Score Breakdown */}
          {healthBreakdown && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Health Breakdown</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Activity</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            'h-full rounded-full',
                            healthBreakdown.activityScore >= 25 ? 'bg-green-500' :
                            healthBreakdown.activityScore >= 15 ? 'bg-amber-500' :
                            'bg-red-500'
                          )}
                          style={{ width: `${(healthBreakdown.activityScore / 30) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8">{healthBreakdown.activityScore}/30</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Errors</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            'h-full rounded-full',
                            healthBreakdown.errorScore >= 20 ? 'bg-green-500' :
                            healthBreakdown.errorScore >= 10 ? 'bg-amber-500' :
                            'bg-red-500'
                          )}
                          style={{ width: `${(healthBreakdown.errorScore / 25) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8">{healthBreakdown.errorScore}/25</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Usage</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            'h-full rounded-full',
                            healthBreakdown.usageScore >= 12 ? 'bg-green-500' :
                            healthBreakdown.usageScore >= 8 ? 'bg-amber-500' :
                            'bg-red-500'
                          )}
                          style={{ width: `${(healthBreakdown.usageScore / 15) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8">{healthBreakdown.usageScore}/15</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Profile</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            'h-full rounded-full',
                            healthBreakdown.profileScore >= 8 ? 'bg-green-500' :
                            healthBreakdown.profileScore >= 5 ? 'bg-amber-500' :
                            'bg-red-500'
                          )}
                          style={{ width: `${(healthBreakdown.profileScore / 10) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8">{healthBreakdown.profileScore}/10</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Payments</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            'h-full rounded-full',
                            healthBreakdown.paymentScore >= 20 ? 'bg-green-500' :
                            'bg-red-500'
                          )}
                          style={{ width: `${(healthBreakdown.paymentScore / 20) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8">{healthBreakdown.paymentScore}/20</span>
                    </div>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">Total Score</span>
                    <span className={cn(
                      'text-lg font-bold',
                      healthBreakdown.status === 'healthy' ? 'text-green-500' :
                      healthBreakdown.status === 'at_risk' ? 'text-amber-500' :
                      'text-red-500'
                    )}>
                      {healthBreakdown.totalScore}/100
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Quick Info Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Account Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">User ID</span>
                <span className="font-mono text-xs">{user.id.slice(0, 8)}...</span>
              </div>
              {user.organizationId && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Org ID</span>
                  <span className="font-mono text-xs">{user.organizationId.slice(0, 8)}...</span>
                </div>
              )}
              {user.stripeCustomerId && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Stripe ID</span>
                  <span className="font-mono text-xs">{user.stripeCustomerId.slice(0, 12)}...</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Reset Flows Dialog */}
      {showResetDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Reset Monthly Flows</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-500">
                This will reset the user&apos;s monthly flow count to 0. Please provide a reason.
              </p>
              <Textarea
                placeholder="Reason for reset..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowResetDialog(false); setActionReason('') }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleResetFlows}
                  disabled={!actionReason.trim() || actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Reset Flows
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Add Flows Dialog */}
      {showAddFlowsDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Add Bonus Flows</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-500">
                This will create a new flow pack with the specified number of bonus flows.
              </p>
              <div>
                <label className="text-sm font-medium">Number of Flows</label>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={flowsToAdd}
                  onChange={(e) => setFlowsToAdd(parseInt(e.target.value) || 5)}
                />
              </div>
              <Textarea
                placeholder="Reason for bonus flows..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowAddFlowsDialog(false); setActionReason(''); setFlowsToAdd(5) }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleAddFlows}
                  disabled={!actionReason.trim() || flowsToAdd < 1 || actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Add {flowsToAdd} Flows
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Extend Trial Dialog */}
      {showExtendTrialDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Extend Trial Period</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-500">
                Extend the user&apos;s trial period by the specified number of days.
                {user.trialEndsAt && (
                  <span className="block mt-1">
                    Current trial ends: <strong>{new Date(user.trialEndsAt).toLocaleDateString()}</strong>
                  </span>
                )}
              </p>
              <div>
                <label className="text-sm font-medium">Days to Extend</label>
                <Input
                  type="number"
                  min={1}
                  max={90}
                  value={daysToExtend}
                  onChange={(e) => setDaysToExtend(parseInt(e.target.value) || 7)}
                />
              </div>
              <Textarea
                placeholder="Reason for trial extension..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowExtendTrialDialog(false); setActionReason(''); setDaysToExtend(7) }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleExtendTrial}
                  disabled={!actionReason.trim() || daysToExtend < 1 || actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Extend by {daysToExtend} Days
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Add Note Dialog */}
      {showNoteDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Add Admin Note</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Enter your note..."
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
                rows={4}
              />
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notePinned}
                  onChange={(e) => setNotePinned(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Pin this note</span>
              </label>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowNoteDialog(false); setNoteContent(''); setNotePinned(false) }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleAddNote}
                  disabled={!noteContent.trim() || actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Add Note
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Edit Note Dialog */}
      {showEditNoteDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Edit Note</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Enter your note..."
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
                rows={4}
              />
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notePinned}
                  onChange={(e) => setNotePinned(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Pin this note</span>
              </label>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowEditNoteDialog(false); setNoteContent(''); setNotePinned(false); setEditingNoteId(null) }}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleEditNote}
                  disabled={!noteContent.trim() || actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Note Dialog */}
      {showDeleteNoteDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Delete Note</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-slate-500">
                Are you sure you want to delete this note? This action cannot be undone.
              </p>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => { setShowDeleteNoteDialog(false); setEditingNoteId(null) }}>
                  Cancel
                </Button>
                <Button 
                  variant="destructive"
                  onClick={handleDeleteNote}
                  disabled={actionLoading}
                >
                  {actionLoading ? <Icons.spinner className="h-4 w-4 animate-spin mr-2" /> : null}
                  Delete Note
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
