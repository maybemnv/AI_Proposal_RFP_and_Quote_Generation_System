import {Field} from "@/components/Field";

type DiscountControlProps = {discount: string; tax: string; onDiscountChange: (value: string) => void; onTaxChange: (value: string) => void};

export function DiscountControl({discount, tax, onDiscountChange, onTaxChange}: DiscountControlProps) {
  return <div className="form-row discount-control"><Field id="discount" label="Discount" inputMode="decimal" value={discount} onChange={(event) => onDiscountChange(event.target.value)} hint="Minor-unit conversion happens at calculation time." /><Field id="tax" label="Tax" inputMode="decimal" value={tax} onChange={(event) => onTaxChange(event.target.value)} /></div>;
}
