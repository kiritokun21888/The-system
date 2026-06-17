import { Card3D } from "@/components/effects/Card3D";
import { Sparkline } from "@/components/charts/Sparkline";
import { NeonText } from "@/components/effects/BeamCard";

/** A single 3D-hover stat tile with a mini sparkline (left panel). */
export function StatCard({
  label,
  value,
  unit,
  color = "#00D2FF",
  spark,
}: {
  label: string;
  value: string | number;
  unit?: string;
  color?: string;
  spark: number[];
}) {
  return (
    <Card3D className="!p-3">
      <div className="text-[9px] font-display uppercase tracking-widest text-[var(--text-dim)]">
        {label}
      </div>
      <div className="mt-0.5 flex items-end gap-1">
        <NeonText color={color} className="text-xl font-bold leading-none">
          {value}
        </NeonText>
        {unit && <span className="mb-0.5 text-[10px] text-[var(--text-dim)]">{unit}</span>}
      </div>
      <div className="mt-1">
        <Sparkline data={spark.length > 1 ? spark : [0, 0]} color={color} />
      </div>
    </Card3D>
  );
}
