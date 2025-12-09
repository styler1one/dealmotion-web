'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { 
  Loader2, 
  Building2, 
  Users, 
  FileText,
  Clock,
  Flame,
  Mic,
  Sparkles
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface ExternalRecording {
  id: string
  provider: string
  external_id: string
  title: string | null
  recording_date: string
  duration_seconds: number | null
  participants: string[]
  matched_meeting_id: string | null
  matched_prospect_id: string | null
}

interface Prospect {
  id: string
  company_name: string
  status: string
}

interface Contact {
  id: string
  name: string
  role?: string
}

interface Preparation {
  id: string
  meeting_subject: string
  created_at: string
}

interface ImportRecordingModalProps {
  isOpen: boolean
  onClose: () => void
  recording: ExternalRecording | null
  onImported: (followupId: string) => void
}

export function ImportRecordingModal({
  isOpen,
  onClose,
  recording,
  onImported
}: ImportRecordingModalProps) {
  const router = useRouter()
  const { toast } = useToast()
  
  // Form state
  const [prospectId, setProspectId] = useState<string>('')
  const [contactIds, setContactIds] = useState<string[]>([])
  const [prepId, setPrepId] = useState<string>('')
  
  // Data state
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [contacts, setContacts] = useState<Contact[]>([])
  const [preparations, setPreparations] = useState<Preparation[]>([])
  
  // Loading state
  const [loadingProspects, setLoadingProspects] = useState(true)
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [loadingPreps, setLoadingPreps] = useState(false)
  const [importing, setImporting] = useState(false)

  // Load prospects on mount
  useEffect(() => {
    if (isOpen) {
      loadProspects()
    }
  }, [isOpen])

  // Pre-fill prospect if matched
  useEffect(() => {
    if (recording?.matched_prospect_id && prospects.length > 0) {
      setProspectId(recording.matched_prospect_id)
    }
  }, [recording, prospects])

  // Load contacts and preps when prospect changes
  useEffect(() => {
    if (prospectId) {
      loadContacts(prospectId)
      loadPreparations(prospectId)
    } else {
      setContacts([])
      setPreparations([])
      setContactIds([])
      setPrepId('')
    }
  }, [prospectId])

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setProspectId('')
      setContactIds([])
      setPrepId('')
    }
  }, [isOpen])

  const loadProspects = async () => {
    setLoadingProspects(true)
    try {
      const { data } = await api.get<{ prospects: Prospect[] }>('/api/v1/prospects?limit=50')
      setProspects(data?.prospects || [])
    } catch (err) {
      console.error('Failed to load prospects:', err)
    } finally {
      setLoadingProspects(false)
    }
  }

  const loadContacts = async (pid: string) => {
    setLoadingContacts(true)
    try {
      const { data } = await api.get<{ contacts: Contact[] }>(`/api/v1/prospects/${pid}/contacts`)
      setContacts(data?.contacts || [])
    } catch (err) {
      console.error('Failed to load contacts:', err)
      setContacts([])
    } finally {
      setLoadingContacts(false)
    }
  }

  const loadPreparations = async (pid: string) => {
    setLoadingPreps(true)
    try {
      // Get preparations for this prospect
      const { data } = await api.get<{ preparations: Preparation[] }>(
        `/api/v1/prep/briefs?prospect_id=${pid}&limit=10`
      )
      setPreparations(data?.preparations || [])
    } catch (err) {
      console.error('Failed to load preparations:', err)
      setPreparations([])
    } finally {
      setLoadingPreps(false)
    }
  }

  const handleImport = async () => {
    if (!recording) return
    
    setImporting(true)
    try {
      // Determine the correct endpoint based on provider
      const provider = recording.provider || 'fireflies'
      const endpoint = provider === 'teams' 
        ? `/api/v1/integrations/teams/recordings/${recording.id}/import`
        : `/api/v1/integrations/fireflies/import/${recording.id}`
      
      const { data, error } = await api.post<{
        success: boolean
        followup_id: string
        message: string
      }>(endpoint, {
        prospect_id: prospectId || null,
        contact_ids: contactIds.length > 0 ? contactIds : null,
        meeting_prep_id: prepId || null
      })
      
      if (error) {
        throw new Error(error.message || 'Import failed')
      }
      
      toast({
        title: 'Recording imported',
        description: data?.message || 'AI analysis in progress',
      })
      
      onClose()
      
      if (data?.followup_id) {
        onImported(data.followup_id)
        router.push(`/dashboard/followup/${data.followup_id}`)
      }
    } catch (err) {
      console.error('Import failed:', err)
      toast({
        title: 'Import failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      })
    } finally {
      setImporting(false)
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '--'
    const mins = Math.floor(seconds / 60)
    if (mins < 60) return `${mins} min`
    const hours = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hours}h ${remainingMins}m`
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'fireflies':
        return <Flame className="h-4 w-4 text-orange-500" />
      case 'teams':
        return <span className="text-[#6264A7] text-xs font-bold">T</span>
      default:
        return <Mic className="h-4 w-4 text-pink-500" />
    }
  }

  if (!recording) return null

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mic className="h-5 w-5 text-pink-500" />
            Import Recording
          </DialogTitle>
        </DialogHeader>

        {/* Recording Info */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-sm shrink-0">
              {getProviderIcon(recording.provider)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 dark:text-white truncate">
                {recording.title || 'Untitled Recording'}
              </p>
              <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
                <Clock className="h-3.5 w-3.5" />
                <span>{formatDuration(recording.duration_seconds)}</span>
                <span>•</span>
                <span className="capitalize">{recording.provider}</span>
                <span>•</span>
                <span>{formatDate(recording.recording_date)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4 py-2">
          {/* Prospect Selector */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-slate-400" />
              Link to Prospect
              <span className="text-xs text-slate-400 font-normal">(optional)</span>
            </Label>
            <Select value={prospectId || "none"} onValueChange={(v) => setProspectId(v === "none" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder={loadingProspects ? "Loading..." : "Select a prospect..."} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No prospect</SelectItem>
                {prospects.map(p => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.company_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {recording.matched_prospect_id && prospectId === recording.matched_prospect_id && (
              <p className="text-xs text-green-600 flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                Auto-detected from calendar meeting
              </p>
            )}
          </div>

          {/* Contact Selector */}
          {prospectId && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Users className="h-4 w-4 text-slate-400" />
                Link to Contacts
                <span className="text-xs text-slate-400 font-normal">(optional)</span>
              </Label>
              {loadingContacts ? (
                <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading contacts...
                </div>
              ) : contacts.length === 0 ? (
                <p className="text-sm text-slate-500 py-2">No contacts found for this prospect</p>
              ) : (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {contacts.map(contact => (
                    <div key={contact.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={`contact-${contact.id}`}
                        checked={contactIds.includes(contact.id)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setContactIds([...contactIds, contact.id])
                          } else {
                            setContactIds(contactIds.filter(id => id !== contact.id))
                          }
                        }}
                      />
                      <Label 
                        htmlFor={`contact-${contact.id}`} 
                        className="text-sm font-normal cursor-pointer"
                      >
                        {contact.name}
                        {contact.role && (
                          <span className="text-slate-400 ml-1">• {contact.role}</span>
                        )}
                      </Label>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Preparation Selector */}
          {prospectId && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-slate-400" />
                Link to Preparation
                <span className="text-xs text-slate-400 font-normal">(optional)</span>
              </Label>
              {loadingPreps ? (
                <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading preparations...
                </div>
              ) : preparations.length === 0 ? (
                <p className="text-sm text-slate-500 py-2">No preparations found for this prospect</p>
              ) : (
                <Select value={prepId || "none"} onValueChange={(v) => setPrepId(v === "none" ? "" : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a preparation..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No preparation</SelectItem>
                    {preparations.map(p => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.meeting_subject || 'Untitled'} - {new Date(p.created_at).toLocaleDateString()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          )}

        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={importing}>
            Cancel
          </Button>
          <Button onClick={handleImport} disabled={importing}>
            {importing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Import & Analyze
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

