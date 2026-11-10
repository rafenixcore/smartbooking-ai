export function formatDate(value: string | null | undefined): string {
  if (!value) return 'No disponible'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? 'No disponible'
    : new Intl.DateTimeFormat('es-DO', { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}
