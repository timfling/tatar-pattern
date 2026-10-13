import { motion, AnimatePresence } from "motion/react";
import { useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";

type AuthFieldProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: "email" | "password" | "text";
  autoComplete?: string;
  action?: ReactNode;
  /** Показать зелёную галочку справа (подтверждённая почта). */
  confirmed?: boolean;
  onConfirmedClick?: () => void;
  /** На мобайле поле и плейсхолдер по центру — как на экране входа. */
  mobileCenter?: boolean;
  className?: string;
};

/**
 * Капсула поля входа/регистрации. Пароль рисуется точками, как в макете,
 * поверх настоящего input — чтобы не зависеть от системных буллитов.
 */
export function AuthField({
  value,
  onChange,
  placeholder,
  type = "text",
  autoComplete,
  action,
  confirmed = false,
  onConfirmedClick,
  mobileCenter = false,
  className = "",
}: AuthFieldProps) {
  const isPassword = type === "password";
  const [visible, setVisible] = useState(false);
  return (
    <div
      className={[
        "relative flex w-full items-center overflow-hidden rounded-[48px] outline outline-[0.5px] -outline-offset-[0.5px] outline-[#676767]",
        "h-[67px] max-md:h-[47px] max-md:rounded-[28px] max-md:outline-[0.3px]",
        className,
      ].join(" ")}
    >
      <input
        aria-label={type === "password" ? "Пароль" : type === "email" ? "Электронная почта" : placeholder}
        maxLength={type === "password" ? 128 : 254}
        type={isPassword ? (visible ? "text" : "password") : type === "email" ? "email" : "text"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        readOnly={confirmed}
        onClick={confirmed ? onConfirmedClick : undefined}
        className={[
          "relative z-0 min-w-0 flex-1 bg-transparent outline-none placeholder:opacity-50",
          "px-[32px] text-[24px] leading-[24px] tracking-[0.01em] text-ink-strong",
          "max-md:px-[18px] max-md:text-[18px] max-md:leading-[18px]",
          "placeholder:font-normal placeholder:text-black max-md:placeholder:text-[16px] max-md:placeholder:leading-[16px] max-md:placeholder:text-black",
          value && !isPassword
            ? "font-[family-name:var(--font-instrument)] font-medium"
            : "font-normal",
          isPassword ? "font-mono tracking-normal pr-[80px]" : "",
          confirmed ? "cursor-pointer pr-[56px]" : action ? (isPassword ? "pr-[210px] max-md:pr-[102px]" : "pr-[160px] max-md:pr-[58px]") : "",
          mobileCenter ? "text-left" : "",
        ].join(" ")}
      />

      {confirmed ? (
        <button
          type="button"
          aria-label="Изменить почту"
          onClick={onConfirmedClick}
          className="absolute right-[24px] top-1/2 -translate-y-1/2 max-md:right-[16px]"
        >
          <span className="text-xl text-ink-muted" aria-hidden>✎</span>
        </button>
      ) : null}

      {isPassword ? <button type="button" aria-label={visible ? "Скрыть пароль" : "Показать пароль"} aria-pressed={visible} onClick={() => setVisible(v => !v)} className={`absolute z-[3] top-1/2 -translate-y-1/2 p-2 ${action ? "right-[160px] max-md:right-[52px]" : "right-4"}`}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>{visible ? <path d="M3 3l18 18" stroke="currentColor" strokeWidth="1.5"/> : null}</svg></button> : null}
      {action && !confirmed ? (
        <span className="absolute right-[6px] top-1/2 z-[2] -translate-y-1/2 max-md:right-[4px]">
          {action}
        </span>
      ) : null}
    </div>
  );
}

type NextButtonProps = {
  onClick: () => void;
  disabled?: boolean;
  /** Пустое поле: тусклый круг. Заполненное: «Далее». На мобайле — только стрелка. */
  filled?: boolean;
  label?: string;
};

export function NextButton({
  onClick,
  disabled = false,
  filled = false,
  label = "Далее",
}: NextButtonProps) {
  return <>
    <motion.button layout type="button" aria-label={label} onClick={onClick} disabled={disabled || !filled} transition={{duration:.3,ease:[.22,1,.36,1]}} className={`hidden h-[55px] items-center justify-center gap-3 rounded-full px-[17px] text-[22px] font-semibold text-[#343434] outline outline-[.5px] outline-[#7f7f7f] disabled:opacity-35 md:flex ${filled ? "[background-image:var(--gradient-gold)]" : "bg-transparent"}`}>
      <AnimatePresence initial={false}>{filled ? <motion.span initial={{opacity:0,width:0}} animate={{opacity:1,width:"auto"}} exit={{opacity:0,width:0}} className="overflow-hidden whitespace-nowrap">{label}</motion.span> : null}</AnimatePresence>
      <Icon name="d17988df" width={23} height={19} />
    </motion.button>
    <button type="button" aria-label={label} onClick={onClick} disabled={disabled || !filled} className="pressable-icon disabled:opacity-30 md:hidden"><Icon name="3cb33f0f" width={50} height={39} /></button>
  </>;
}

type ContinueButtonProps = {
  disabled: boolean;
  children: ReactNode;
};

export function ContinueButton({ disabled, children }: ContinueButtonProps) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className={[
        "inline-flex h-[55px] items-center gap-[12px] rounded-[48px] px-[20px] text-[22px] font-semibold leading-[22px] tracking-[0.01em] text-[#343434] outline outline-[0.5px] -outline-offset-[0.5px] outline-[#7F7F7F] disabled:opacity-100",
        "max-md:h-[41px] max-md:gap-[9px] max-md:rounded-[36px] max-md:px-[15px] max-md:text-[16px] max-md:leading-[16px]",
        disabled
          ? "cursor-default [background-image:var(--gradient-gold-dim)]"
          : "pressable [background-image:var(--gradient-gold-strong)]",
      ].join(" ")}
    >
      <span className={disabled ? "opacity-30" : ""}>{children}</span>
      {disabled ? (
        <>
          <Icon
            name="8e536377"
            width={23}
            height={19}
            className="hidden md:block"
          />
          <Icon
            name="71f525b3"
            width={17}
            height={14}
            className="opacity-30 md:hidden"
          />
        </>
      ) : (
        <>
          <Icon
            name="858e112d"
            width={23}
            height={19}
            className="hidden md:block"
          />
          <Icon
            name="ce552603"
            width={17}
            height={14}
            className="md:hidden"
          />
        </>
      )}
    </button>
  );
}
