import type { Metadata } from "next";

import { ShipmentsList } from "@/components/shipments/shipment-pages";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Shipments · Whitespace" };

export default function ShipmentsPage() {
  return <ShipmentsList />;
}
