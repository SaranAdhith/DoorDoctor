import { Camera, Check } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { attachmentObjectUrl, medicationDepthApi } from '../../api/trust'
import { Button, useToast } from '../ui'
import type { MedicationLog } from '../../types'

/**
 * The dose confirmation photograph (§4.12).
 *
 * `capture="environment"` opens the camera directly on a phone, which is where
 * this is used — a nurse standing in a hallway should not have to go through a
 * file picker.
 *
 * The thumbnail is fetched **with the bearer token and rendered from an object
 * URL**, because uploads are never served statically: an `<img src>` pointing at
 * the API would arrive unauthenticated and 401. The object URL is revoked when
 * the row unmounts so a long visit does not leak a blob per dose.
 */
export function DosePhotoButton({
  log,
  disabled,
  onUploaded,
}: {
  log: MedicationLog
  disabled?: boolean
  onUploaded: (log: MedicationLog) => void
}) {
  const { notify } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => {
    let revoked: string | null = null
    if (log.photo) {
      attachmentObjectUrl(log.photo)
        .then((url) => {
          revoked = url
          setPreview(url)
        })
        .catch(() => setPreview(null))
    } else {
      setPreview(null)
    }
    return () => {
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [log.photo?.id])

  async function upload(file: File) {
    setBusy(true)
    try {
      const updated = await medicationDepthApi.uploadPhoto(log.id, file)
      notify('Photo saved with this dose.', 'success')
      onUploaded(updated)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not upload that photo.', 'error')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="flex items-center gap-2">
      {preview && (
        <img
          src={preview}
          alt="Photograph taken when this dose was given"
          className="h-10 w-10 rounded-md object-cover ring-1 ring-border-subtle"
        />
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void upload(file)
        }}
      />
      <Button
        size="sm"
        variant="ghost"
        disabled={disabled || busy}
        onClick={() => inputRef.current?.click()}
      >
        {log.photo ? (
          <>
            <Check aria-hidden className="mr-1 h-4 w-4" />
            {busy ? 'Saving…' : 'Retake'}
          </>
        ) : (
          <>
            <Camera aria-hidden className="mr-1 h-4 w-4" />
            {busy ? 'Saving…' : 'Add photo'}
          </>
        )}
      </Button>
    </div>
  )
}
