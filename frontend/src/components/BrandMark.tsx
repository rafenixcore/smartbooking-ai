type BrandMarkProps = {
  className?: string
  size?: number
}

export default function BrandMark({ className = '', size = 40 }: BrandMarkProps) {
  return (
    <img
      src="/smartbooking-turno.svg"
      width={size}
      height={size}
      className={className}
      alt=""
      aria-hidden="true"
    />
  )
}
