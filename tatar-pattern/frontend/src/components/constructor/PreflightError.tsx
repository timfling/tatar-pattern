import { ApiError, apiMessage } from "@/lib/api";

export function PreflightError({ error }: { error: unknown }) {
  const details = error instanceof ApiError ? error.details as {
    minimumSize?: number[]; minimumHeight?: number; minimumWidth?: number;
    suggestion?: string; diagnostics?: {code?:string; reason?:string; message?:string}[];
  } | undefined : undefined;
  const readable=(value:string)=>value.replace(/TP-E-\d+/g,"мотив");
  return <div role="alert" className="mt-2 space-y-2">
    <p>{readable(apiMessage(error))}</p><p>Выбранные элементы сохранены без замены.</p>
    {error instanceof ApiError && error.code === "SCHEME_REGISTRY_CHANGED" ? <p>Обновите каталог схем кнопкой ниже, затем проверьте сохранённый выбор.</p> : null}
    {details?.minimumSize ? <p>Минимальный размер модуля: {details.minimumSize.join(" × ")} px.</p> : null}
    {details?.minimumHeight ? <p>Нужна высота от {details.minimumHeight} px.</p> : null}
    {details?.minimumWidth ? <p>Нужна ширина от {details.minimumWidth} px.</p> : null}
    {details?.suggestion ? <p>{readable(details.suggestion)}</p> : null}
    {details?.diagnostics?.map((d,i) => <p key={i}>{d.code}: {readable(d.reason ?? d.message ?? "")}</p>)}
  </div>;
}
