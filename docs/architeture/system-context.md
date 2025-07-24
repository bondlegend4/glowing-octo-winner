graph TD
    subgraph "Automated Agroforestry Platform"
        direction LR
        A["<div style='font-weight:bold; font-size: 1.2em'>Automated Agroforestry Platform</div><div style='font-size: 0.9em'>Provides cost/profit analysis and permaculture design</div>"]
    end

    subgraph "Users"
        direction TB
        U1[Farmer / Land Owner]
        U2[Permaculture Designer]
        U3[Investor]
    end

    subgraph "External Systems"
        direction TB
        ES1[USGS APIs<br/>(Elevation Data)]
        ES2[State/County GIS<br/>(Zoning & Parcel Data)]
        ES3[Real Estate APIs<br/>(Land for Sale)]
        ES4[GBIF / USDA<br/>(Plant Databases)]
        ES5[Grants.gov API<br/>(Federal Grants)]
    end

    U1 --> A
    U2 --> A
    U3 --> A
    A --> ES1
    A --> ES2
    A --> ES3
    A --> ES4
    A --> ES5