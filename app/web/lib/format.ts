export function formatMinor(minor: number, currency = "USD"): string {
  const sign = minor < 0 ? "-" : "";
  const digits = String(Math.abs(Math.trunc(minor))).padStart(3, "0");
  const whole = digits.slice(0, -2) || "0";
  const fraction = digits.slice(-2);
  return `${sign}${Number(whole).toLocaleString("en-US")}.${fraction} ${currency}`;
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
