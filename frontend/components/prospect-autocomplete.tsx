'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Search, Building2, FileText, Briefcase, MessageSquare, Check, Loader2 } from 'lucide-react'

// API response from prospects endpoint
interface ProspectApiResponse {
    id: string
    company_name: string
    status: string
    industry?: string
    last_activity_at: string
    research_count?: number
    prep_count?: number
    followup_count?: number
}

// Enriched prospect with computed fields
interface Prospect extends ProspectApiResponse {
    // Legacy compatibility fields (computed in component)
    name?: string
    has_research?: boolean
    has_prep?: boolean
    has_followup?: boolean
    context_score?: number
}

interface ProspectAutocompleteProps {
    value: string
    onChange: (value: string, prospectId?: string) => void
    placeholder?: string
    className?: string
    disabled?: boolean
}

export function ProspectAutocomplete({
    value,
    onChange,
    placeholder = "Zoek of voer bedrijfsnaam in...",
    className,
    disabled = false
}: ProspectAutocompleteProps) {
    const supabase = createClientComponentClient()
    const [isOpen, setIsOpen] = useState(false)
    const [prospects, setProspects] = useState<Prospect[]>([])
    const [searchResults, setSearchResults] = useState<Prospect[]>([])
    const [loading, setLoading] = useState(false)
    const [searching, setSearching] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const inputRef = useRef<HTMLInputElement>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)
    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    // Fetch initial prospects on mount (recent ones)
    useEffect(() => {
        const fetchProspects = async () => {
            setLoading(true)
            try {
                const { data: { session } } = await supabase.auth.getSession()
                if (!session) return

                const response = await fetch(
                    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/prospects?limit=20`,
                    {
                        headers: {
                            'Authorization': `Bearer ${session.access_token}`
                        }
                    }
                )

                if (response.ok) {
                    const data = await response.json()
                    // Transform to include legacy fields
                    const transformed = (data.prospects || []).map((p: ProspectApiResponse): Prospect => ({
                        ...p,
                        name: p.company_name,
                        has_research: (p.research_count || 0) > 0,
                        has_prep: (p.prep_count || 0) > 0,
                        has_followup: (p.followup_count || 0) > 0,
                        context_score: (p.research_count || 0) + (p.prep_count || 0) + (p.followup_count || 0)
                    }))
                    setProspects(transformed)
                }
            } catch (error) {
                console.error('Error fetching prospects:', error)
            } finally {
                setLoading(false)
            }
        }

        fetchProspects()
    }, [supabase])

    // Search prospects with debounce
    const searchProspects = useCallback(async (query: string) => {
        if (query.length < 2) {
            setSearchResults([])
            return
        }

        setSearching(true)
        try {
            const { data: { session } } = await supabase.auth.getSession()
            if (!session) return

            const response = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL}/api/v1/prospects/search?q=${encodeURIComponent(query)}&limit=10`,
                {
                    headers: {
                        'Authorization': `Bearer ${session.access_token}`
                    }
                }
            )

            if (response.ok) {
                const data = await response.json()
                // Transform to include legacy fields
                const transformed = data.map((p: ProspectApiResponse): Prospect => ({
                    ...p,
                    name: p.company_name,
                    has_research: false, // Search endpoint doesn't return counts
                    has_prep: false,
                    has_followup: false,
                    context_score: 0
                }))
                setSearchResults(transformed)
            }
        } catch (error) {
            console.error('Error searching prospects:', error)
        } finally {
            setSearching(false)
        }
    }, [supabase])

    // Debounced search when typing
    useEffect(() => {
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current)
        }

        if (value.trim().length >= 2) {
            searchTimeoutRef.current = setTimeout(() => {
                searchProspects(value.trim())
            }, 300)
        } else {
            setSearchResults([])
        }

        return () => {
            if (searchTimeoutRef.current) {
                clearTimeout(searchTimeoutRef.current)
            }
        }
    }, [value, searchProspects])

    // Get filtered prospects (search results or filter from cached)
    const filteredProspects = value.trim().length >= 2 
        ? searchResults 
        : prospects.slice(0, 10)

    // Handle keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (!isOpen) {
            if (e.key === 'ArrowDown' && filteredProspects.length > 0) {
                setIsOpen(true)
                setSelectedIndex(0)
                e.preventDefault()
            }
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                setSelectedIndex(prev => 
                    prev < filteredProspects.length - 1 ? prev + 1 : prev
                )
                break
            case 'ArrowUp':
                e.preventDefault()
                setSelectedIndex(prev => prev > 0 ? prev - 1 : prev)
                break
            case 'Enter':
                e.preventDefault()
                if (selectedIndex >= 0 && filteredProspects[selectedIndex]) {
                    selectProspect(filteredProspects[selectedIndex])
                }
                break
            case 'Escape':
                setIsOpen(false)
                setSelectedIndex(-1)
                break
        }
    }, [isOpen, selectedIndex, filteredProspects])

    const selectProspect = (prospect: Prospect) => {
        onChange(prospect.company_name || prospect.name || '', prospect.id)
        setIsOpen(false)
        setSelectedIndex(-1)
        inputRef.current?.blur()
    }

    // Close dropdown on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (
                dropdownRef.current && 
                !dropdownRef.current.contains(e.target as Node) &&
                !inputRef.current?.contains(e.target as Node)
            ) {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    // Check if current value matches a known prospect
    const isKnownProspect = prospects.some(
        p => (p.company_name || p.name || '').toLowerCase() === value.toLowerCase()
    )
    
    // Find matched prospect for additional info
    const matchedProspect = prospects.find(
        p => (p.company_name || p.name || '').toLowerCase() === value.toLowerCase()
    )

    return (
        <div className={cn("relative", className)}>
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    ref={inputRef}
                    type="text"
                    value={value}
                    onChange={(e) => {
                        onChange(e.target.value)
                        setIsOpen(true)
                        setSelectedIndex(-1)
                    }}
                    onFocus={() => setIsOpen(true)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    className={cn(
                        "pl-10 pr-10",
                        isKnownProspect && "border-green-500 focus-visible:ring-green-500"
                    )}
                />
                {searching && (
                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground animate-spin" />
                )}
                {!searching && isKnownProspect && (
                    <Check className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-green-500" />
                )}
            </div>

            {/* Dropdown */}
            {isOpen && (filteredProspects.length > 0 || value.trim()) && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-[300px] overflow-auto"
                >
                    {filteredProspects.length > 0 ? (
                        <>
                            <div className="px-3 py-2 text-xs text-muted-foreground border-b bg-muted/50 flex items-center justify-between">
                                <span>Bekende prospects ({filteredProspects.length})</span>
                                {searching && <Loader2 className="h-3 w-3 animate-spin" />}
                            </div>
                            {filteredProspects.map((prospect, index) => (
                                <div
                                    key={prospect.id || prospect.name}
                                    className={cn(
                                        "px-3 py-2 cursor-pointer flex items-center justify-between",
                                        "hover:bg-accent",
                                        selectedIndex === index && "bg-accent"
                                    )}
                                    onClick={() => selectProspect(prospect)}
                                    onMouseEnter={() => setSelectedIndex(index)}
                                >
                                    <div className="flex items-center gap-2">
                                        <Building2 className="h-4 w-4 text-muted-foreground" />
                                        <div>
                                            <span className="font-medium">{prospect.company_name || prospect.name}</span>
                                            {prospect.industry && (
                                                <span className="text-xs text-muted-foreground ml-2">• {prospect.industry}</span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        {prospect.has_research && (
                                            <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                <FileText className="h-3 w-3 mr-1" />
                                                Research
                                            </Badge>
                                        )}
                                        {prospect.has_prep && (
                                            <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                <Briefcase className="h-3 w-3 mr-1" />
                                                Prep
                                            </Badge>
                                        )}
                                        {prospect.has_followup && (
                                            <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                <MessageSquare className="h-3 w-3 mr-1" />
                                                Follow-up
                                            </Badge>
                                        )}
                                        {prospect.status && prospect.status !== 'new' && (
                                            <Badge variant="secondary" className="text-xs px-1.5 py-0 capitalize">
                                                {prospect.status}
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </>
                    ) : value.trim() ? (
                        <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                            {searching ? (
                                <>
                                    <Loader2 className="h-8 w-8 mx-auto mb-2 animate-spin opacity-50" />
                                    <p>Zoeken...</p>
                                </>
                            ) : (
                                <>
                                    <Building2 className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p>Geen bekende prospect gevonden</p>
                                    <p className="text-xs mt-1">
                                        Druk Enter om "{value}" te gebruiken als nieuwe prospect
                                    </p>
                                </>
                            )}
                        </div>
                    ) : null}
                </div>
            )}

            {/* Helper text */}
            {!isOpen && !isKnownProspect && value.trim() && (
                <p className="text-xs text-amber-600 mt-1">
                    ⚠️ Nieuwe prospect - wordt automatisch aangemaakt
                </p>
            )}
            {!isOpen && isKnownProspect && matchedProspect && (
                <p className="text-xs text-green-600 mt-1">
                    ✓ Bekende prospect{matchedProspect.context_score && matchedProspect.context_score > 0 ? ` - ${matchedProspect.context_score} activiteit(en)` : ''}
                </p>
            )}
        </div>
    )
}

