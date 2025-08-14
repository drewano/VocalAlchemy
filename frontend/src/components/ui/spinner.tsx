import { LoaderCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface SpinnerProps {
  text?: string
  className?: string
}

export function Spinner({ text, className }: SpinnerProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-4 p-8 text-muted-foreground", className)}>
      <LoaderCircle className="h-10 w-10 animate-spin" />
      {text && <p className="text-center">{text}</p>}
    </div>
  )
}
