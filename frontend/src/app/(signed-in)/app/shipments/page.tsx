import type { Metadata } from "next";

import { ShipmentsList } from "@/components/shipments/shipment-pages";

export const metadata: Metadata = { title: "Shipments · Whitespace" };

export default function ShipmentsPage() {
  return <ShipmentsList />;
}
