import { useEffect, useState } from 'react';

interface NumericInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  disabled?: boolean;
  isDecimal?: boolean;
}

/**
 * Responsive numeric input that maintains a local string draft state.
 * Allows empty input during editing, preserves keyboard navigation,
 * paste, and multi-digit entry, and only validates and commits on blur or Enter.
 */
export default function NumericInput({
  label,
  value,
  onChange,
  min = 1,
  max = 100,
  step = 1,
  unit,
  disabled = false,
  isDecimal = false,
}: NumericInputProps) {
  const [draft, setDraft] = useState<string>(String(value));
  const [isFocused, setIsFocused] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Synchronize draft when parent value changes, but only if user is not actively typing
  useEffect(() => {
    if (!isFocused) {
      setDraft(String(value));
      setValidationError(null);
    }
  }, [value, isFocused]);

  const commitValue = () => {
    const trimmed = draft.trim();
    if (trimmed === '') {
      // Revert to current valid value if empty on blur
      setDraft(String(value));
      setValidationError(null);
      return;
    }

    const parsed = isDecimal ? parseFloat(trimmed) : parseInt(trimmed, 10);
    if (Number.isNaN(parsed)) {
      setValidationError('Enter a valid number');
      setDraft(String(value));
      return;
    }

    if (parsed < min) {
      setValidationError(`Clamped to min (${min})`);
      setDraft(String(min));
      onChange(min);
      return;
    }

    if (parsed > max) {
      setValidationError(`Clamped to max (${max})`);
      setDraft(String(max));
      onChange(max);
      return;
    }

    setValidationError(null);
    const finalVal = isDecimal ? Math.round(parsed * 100) / 100 : parsed;
    setDraft(String(finalVal));
    onChange(finalVal);
  };

  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <span className="number-wrap">
        <input
          type="text"
          inputMode={isDecimal ? 'decimal' : 'numeric'}
          step={step}
          value={draft}
          disabled={disabled}
          onChange={(event) => {
            setDraft(event.target.value);
            if (validationError) setValidationError(null);
          }}
          onFocus={() => setIsFocused(true)}
          onBlur={() => {
            setIsFocused(false);
            commitValue();
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.currentTarget.blur();
            }
          }}
          aria-label={label}
        />
        {unit && <span>{unit}</span>}
      </span>
      {validationError && (
        <span className="field-error-text" role="alert">
          {validationError}
        </span>
      )}
    </label>
  );
}
