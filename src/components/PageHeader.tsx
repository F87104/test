import Link from "next/link";

export function PageHeader({
  icon,
  title,
  description,
}: {
  icon?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-8">
      <div className="text-xs text-ink-500 mb-2">
        <Link href="/" className="hover:text-brand-700">
          ホーム
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-ink-700">{title}</span>
      </div>
      <div className="flex items-start gap-3">
        {icon && (
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-2xl shadow-soft">
            {icon}
          </span>
        )}
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-950">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-ink-600 leading-relaxed max-w-2xl">
              {description}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
