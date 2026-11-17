"use client";

/** The trend chart of one metric (U-06-T06), drawn with Recharts; the figures also open as a
 * table under it (screen readers, exact values). */
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TrendPoint {
  date: string;
  value: number | null;
}

export interface TrendChartProps {
  label: string;
  points: TrendPoint[];
  format: (value: number) => string;
  formatDate: (iso: string) => string;
}

export function TrendChart({ label, points, format, formatDate }: TrendChartProps) {
  return (
    <div role="img" aria-label={label} className="h-64 w-full" data-trend-chart="">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tickFormatter={formatDate} minTickGap={24} />
          <YAxis tickFormatter={(value: number) => format(value)} width={88} />
          <Tooltip
            labelFormatter={(value) => formatDate(String(value))}
            formatter={(value) => format(Number(value))}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--color-fg-link)"
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
