import { InputHTMLAttributes, forwardRef, useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/utils/cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, id, label, error, type = 'text', ...props }, ref) => {
    const generatedId = useId();
    const [passwordVisible, setPasswordVisible] = useState(false);
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const isPassword = type === 'password';
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-semibold text-foreground mb-2">
            {label}
          </label>
        )}
        <div className="relative">
          <input
            type={isPassword && passwordVisible ? 'text' : type}
            id={inputId}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : props['aria-describedby']}
            className={cn(
              'flex h-11 w-full rounded-control border border-input bg-background px-3 py-2 text-sm transition-colors',
              'file:border-0 file:bg-transparent file:text-sm file:font-medium',
              'placeholder:text-muted-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:border-primary',
              'hover:border-primary/40',
              'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input',
              isPassword && 'pr-12',
              error && 'border-destructive focus-visible:ring-destructive/20 focus-visible:border-destructive hover:border-destructive',
              className
            )}
            ref={ref}
            {...props}
          />
          {isPassword && (
            <button
              type="button"
              aria-label={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              aria-pressed={passwordVisible}
              disabled={props.disabled}
              onClick={() => setPasswordVisible((visible) => !visible)}
              className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {passwordVisible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
            </button>
          )}
        </div>
        {error && (
          <p id={errorId} className="mt-2 text-sm font-medium text-destructive">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
