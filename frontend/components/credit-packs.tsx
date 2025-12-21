'use client'

import { useState, useEffect } from 'react'
import { Loader2, Zap, Star, Crown, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface CreditPack {
  id: string
  name: string
  credits: number
  price_cents: number
  per_credit_cents?: number
  description?: string
  popular?: boolean
  best_value?: boolean
}

interface CreditPacksProps {
  className?: string
  onSuccess?: () => void
}

export function CreditPacks({ className, onSuccess }: CreditPacksProps) {
  const { toast } = useToast()
  const [packs, setPacks] = useState<CreditPack[]>([])
  const [loading, setLoading] = useState(true)
  const [purchasing, setPurchasing] = useState<string | null>(null)

  useEffect(() => {
    const fetchPacks = async () => {
      try {
        const response = await api.get<CreditPack[]>('/api/v1/billing/flow-packs/products')
        if (response.data) {
          setPacks(response.data)
        }
      } catch (err) {
        console.error('Failed to load credit packs:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchPacks()
  }, [])

  const handlePurchase = async (packId: string) => {
    setPurchasing(packId)
    try {
      const response = await api.post<{ checkout_url: string }>('/api/v1/billing/flow-packs/checkout', {
        pack_id: packId,
        success_url: `${window.location.origin}/dashboard/settings?credits=success`,
        cancel_url: `${window.location.origin}/dashboard/settings?credits=cancelled`,
      })
      
      if (response.data?.checkout_url) {
        window.location.href = response.data.checkout_url
      } else {
        throw new Error('No checkout URL received')
      }
    } catch (err) {
      console.error('Purchase failed:', err)
      toast({
        title: 'Fout',
        description: 'Kon checkout niet starten. Probeer opnieuw.',
        variant: 'destructive',
      })
    } finally {
      setPurchasing(null)
    }
  }

  const formatPrice = (cents: number) => {
    return new Intl.NumberFormat('nl-NL', {
      style: 'currency',
      currency: 'EUR',
    }).format(cents / 100)
  }

  if (loading) {
    return (
      <div className={cn("flex items-center justify-center p-8", className)}>
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    )
  }

  if (packs.length === 0) {
    return null
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
          Credits Bijkopen
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Koop extra credits om door te gaan met je sales intelligence
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {packs.map((pack) => (
          <Card
            key={pack.id}
            className={cn(
              "relative transition-all hover:shadow-md",
              pack.popular && "border-indigo-500 shadow-indigo-500/10",
              pack.best_value && "border-emerald-500 shadow-emerald-500/10"
            )}
          >
            {pack.popular && (
              <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                <Badge className="bg-indigo-500 text-white text-xs">
                  <Star className="h-3 w-3 mr-1" />
                  Populair
                </Badge>
              </div>
            )}
            {pack.best_value && (
              <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                <Badge className="bg-emerald-500 text-white text-xs">
                  <Crown className="h-3 w-3 mr-1" />
                  Beste Deal
                </Badge>
              </div>
            )}

            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Zap className={cn(
                  "h-5 w-5",
                  pack.popular ? "text-indigo-500" :
                  pack.best_value ? "text-emerald-500" :
                  "text-amber-500"
                )} />
                {pack.name}
              </CardTitle>
              <CardDescription className="text-xs">
                {pack.description || `${pack.credits} credits`}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-3">
              <div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatPrice(pack.price_cents)}
                  </span>
                </div>
                {pack.per_credit_cents && (
                  <p className="text-xs text-slate-500">
                    {formatPrice(pack.per_credit_cents)} per credit
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                  <Check className="h-4 w-4 text-emerald-500" />
                  <span>{pack.credits} credits</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                  <Check className="h-4 w-4 text-emerald-500" />
                  <span>Nooit verlopen</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                  <Check className="h-4 w-4 text-emerald-500" />
                  <span>Direct beschikbaar</span>
                </div>
              </div>

              <Button
                className={cn(
                  "w-full",
                  pack.popular && "bg-indigo-600 hover:bg-indigo-700",
                  pack.best_value && "bg-emerald-600 hover:bg-emerald-700"
                )}
                onClick={() => handlePurchase(pack.id)}
                disabled={purchasing !== null}
              >
                {purchasing === pack.id ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Even geduld...
                  </>
                ) : (
                  <>
                    Kopen
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

