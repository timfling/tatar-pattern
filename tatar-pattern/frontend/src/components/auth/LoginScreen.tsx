"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthField, NextButton } from "@/components/auth/AuthField";
import { emailLooksValid } from "@/lib/auth";

import { api, apiMessage } from "@/lib/api";

type Step = "email" | "password" | "loading";

export function LoginScreen() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const emailReady = emailLooksValid(email);
  const passwordReady = password.length > 0;

  function submitEmail() {
    if (!emailReady) return;
    setStep("password");
  }

  async function submitPassword() {
    if (!passwordReady || step === "loading") return;
    setError(""); setStep("loading");
    try { await api.login(email.trim(), password); router.replace("/constructor"); }
    catch (e) { setError(apiMessage(e)); setStep("password"); }
  }

  if (step === "loading") {
    return (
      <AuthShell mobileHelp>
        <div className="flex flex-1 flex-col items-center justify-center px-[24px]">
          <p className="text-center font-display text-[36px] italic leading-[36px] text-[#656565] max-md:text-[23px] max-md:leading-[23px]">
            Входим в аккаунт…
          </p>
          <div className="relative mt-[64px] h-[6px] w-[200px] overflow-hidden rounded-full bg-[#bfbfbf]/60 max-md:mt-[41px] max-md:h-[4px] max-md:w-[128px]">
            <div
              style={{ width: "40%" }}
              className="api-wait absolute inset-y-0 left-0 rounded-full bg-[#999]"
            />
          </div>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-[24px] max-md:justify-start max-md:pt-[190px]">
        <h1 className="text-center font-display text-[58px] italic leading-[58px] text-[#1B1B1B] max-md:text-[32px] max-md:leading-[32px]">
          Добро пожаловать!
        </h1>

        {step === "email" ? (
          <p className="mt-[25px] flex items-center justify-center gap-[9px] text-[20px] leading-[20px] text-black opacity-80 max-md:hidden">
            <span className="font-normal">Нет аккаунта?</span>
            <Link
              href="/register"
              className="pressable-quiet rounded-full px-[12px] py-[8px]"
            >
              <span className="font-semibold">[</span>
              <span className="font-medium"> Создать новый аккаунт </span>
              <span className="font-semibold">]</span>
            </Link>
          </p>
        ) : null}

        <form
          className={[
            "auth-form flex w-full max-w-[607px] flex-col items-stretch",
            step === "email"
              ? "mt-[90px] max-md:mt-[41px]"
              : "mt-[54px] gap-[16px] max-md:mt-[41px] max-md:gap-[16px]",
          ].join(" ")}
          onSubmit={(event) => {
            event.preventDefault();
            if (step === "email") submitEmail();
            else submitPassword();
          }}
        >
          <AuthField
            type="email"
            value={email}
            onChange={(value) => {
              setEmail(value);
              if (step === "password") setStep("email");
            }}
            placeholder="Введите адрес электронной почты"
            autoComplete="email"
            mobileCenter
            confirmed={step === "password"}
            onConfirmedClick={() => setStep("email")}
            action={
              step === "email" ? (
                <NextButton
                  filled={emailReady}
                  onClick={submitEmail}
                />
              ) : undefined
            }
          />

          {step === "password" ? (
            <div className="page-enter"><AuthField
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="Введите пароль"
              autoComplete="current-password"
              mobileCenter
              action={
                <NextButton
                  filled={passwordReady}
                  onClick={submitPassword}
                />
              }
            /></div>
          ) : null}
          {error ? <p role="alert" className="api-error">{error}</p> : null}
        </form>
      </div>

      {step === "email" ? (
        <div className="flex flex-col items-center pb-[max(32px,env(safe-area-inset-bottom))] pt-[16px] opacity-70 md:hidden">
          <p className="text-[15px] font-normal leading-[15px] text-black">
            Нет аккаунта?
          </p>
          <Link
            href="/register"
            className="pressable-quiet rounded-full px-[12px] py-[6px] text-[16px] font-semibold leading-[16px] text-black"
          >
            [ Создать новый аккаунт ]
          </Link>
        </div>
      ) : null}
    </AuthShell>
  );
}
