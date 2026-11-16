import { createElement } from "react";

import {
  Apple,
  Baby,
  Bath,
  BedDouble,
  Beef,
  BrickWall,
  Briefcase,
  Cable,
  Candy,
  Car,
  CircleDot,
  Citrus,
  Coffee,
  Croissant,
  Droplet,
  Dumbbell,
  Factory,
  Fish,
  FlaskConical,
  Flower2,
  Footprints,
  Gem,
  Hammer,
  Layers,
  type LucideIcon,
  type LucideProps,
  Milk,
  Mountain,
  Nut,
  Package,
  Pill,
  Recycle,
  Scissors,
  Shirt,
  Sofa,
  Sparkles,
  Spool,
  Sprout,
  Stethoscope,
  ToyBrick,
  Trophy,
  UtensilsCrossed,
  Wheat,
  Wine,
  Blocks,
  Grid3x3,
  Carrot,
} from "lucide-react";

// An everyday picture for each niche, so the grid can be scanned without reading.
const NICHE: Record<string, LucideIcon> = {
  "cotton-yarn": Spool,
  "woven-fabrics": Layers,
  "knitted-fabrics": Grid3x3,
  "t-shirts": Shirt,
  knitwear: Shirt,
  "trousers-jeans": Scissors,
  shirts: Shirt,
  socks: Footprints,
  babywear: Baby,
  sportswear: Dumbbell,
  "home-textiles": BedDouble,
  towels: Bath,
  carpets: Grid3x3,
  "leather-apparel": Scissors,
  "leather-goods": Briefcase,
  footwear: Footprints,
  rice: Wheat,
  "tropical-fruit": Apple,
  citrus: Citrus,
  "fresh-vegetables": Carrot,
  nuts: Nut,
  "tea-coffee": Coffee,
  spices: Sprout,
  "fish-seafood": Fish,
  meat: Beef,
  dairy: Milk,
  flowers: Flower2,
  "sugar-confectionery": Candy,
  "bakery-snacks": Croissant,
  "vegetable-oils": Droplet,
  "plastic-raw": Recycle,
  "plastic-products": Package,
  rubber: CircleDot,
  "paper-packaging": Package,
  chemicals: FlaskConical,
  pharma: Pill,
  cosmetics: Sparkles,
  "cement-stone": Mountain,
  "ceramics-glass": Wine,
  steel: BrickWall,
  "aluminium-copper": Blocks,
  surgical: Stethoscope,
  "sports-goods": Trophy,
  toys: ToyBrick,
  furniture: Sofa,
  "cutlery-tools": UtensilsCrossed,
  electrical: Cable,
  "auto-parts": Car,
  jewellery: Gem,
};

const SECTOR: [RegExp, LucideIcon][] = [
  [/textile|apparel|cloth/i, Shirt],
  [/food|agri/i, Wheat],
  [/material|chemical/i, FlaskConical],
  [/manufactur/i, Factory],
];

export function sectorIcon(sector: string): LucideIcon {
  return SECTOR.find(([pattern]) => pattern.test(sector))?.[1] ?? Hammer;
}

export function nicheIcon(slug: string, sector: string): LucideIcon {
  return NICHE[slug] ?? sectorIcon(sector);
}

/** The niche's picture as an element (keeps the icon choice out of render-time components). */
export function NicheIcon({
  slug,
  sector,
  ...props
}: { slug: string; sector: string } & LucideProps) {
  return createElement(nicheIcon(slug, sector), props);
}
