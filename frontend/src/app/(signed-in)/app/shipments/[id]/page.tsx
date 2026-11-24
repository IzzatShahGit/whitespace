import type { Metadata } from "next";

import { ShipmentView } from "@/components/shipments/shipment-pages";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Shipment · Whitespace" };

export default function ShipmentPage({ params }: PageProps<"/app/shipments/[id]">) {
  return <ShipmentView params={params} />;
}
