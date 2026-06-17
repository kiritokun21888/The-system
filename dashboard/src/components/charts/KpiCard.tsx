import { motion } from "framer-motion";
import { BeamCard, NeonText } from "@/components/effects/BeamCard";
import { Sparkline } from "./Sparkline";

/** Large KPI tile with a beam sweep, big animated number, and a sparkline. */
export function KpiCard({
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
  spark?: number[];
}) {
  return (
    <BeamCard color={color}>
      <div className="text-[10px] font-display uppercase tracking-widest text-[var(--text-dim)]">
        {label}
      </div>
      <motion.div
        key={String(value)}
        initial={{ opacity: 0.4, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-1 flex items-end gap-1"
      >
        <NeonText color={color} className="text-3xl font-bold">
          {value}
        </NeonText>
        {unit && <span className="mb-1 text-xs text-[var(--text-dim)]">{unit}</span>}
      </motion.div>
      {spark && spark.length > 1 && (
        <div className="mt-2">
          <Sparkline data={spark} color={color} />
        </div>
      )}
    </BeamCard>
  );
}
