import { useEffect, useState } from 'react'
import { getAudioFileSasUrl } from '@/services/api'
import { Skeleton } from '@/components/ui/skeleton'

type Props = {
  analysisId: string
}

export default function AudioPlayer({ analysisId }: Props) {
  const [audioSrc, setAudioSrc] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      setError(null)
      try {
        const url = await getAudioFileSasUrl(analysisId)
        if (cancelled) return
        setAudioSrc(url)
      } catch (e: any) {
        if (cancelled) return
        setError(e?.message || 'Erreur lors du chargement de l\'audio')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [analysisId])

  if (isLoading) {
    return <Skeleton className="h-10 w-full" />
  }

  if (error) {
    return <div className="text-sm text-destructive">{error}</div>
  }

  if (!audioSrc) {
    return <div className="text-sm text-muted-foreground">Audio indisponible.</div>
  }

  return (
    <audio controls src={audioSrc} className="w-full">
      Votre navigateur ne supporte pas l'élément audio.
    </audio>
  )
}
