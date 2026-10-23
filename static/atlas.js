/* A local electronic map for fictional geography. Geometry is local, deterministic and independent of the save. */
(function (scope) {
  "use strict";
  const W = 960, H = 620;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const clamp = (n, a, b) => Math.max(a, Math.min(b, Number(n) || 0));
  const list = s => Array.isArray(s?.map?.urban) ? s.map.urban : [];
  const countries = s => Array.isArray(s?.map?.countries) ? s.map.countries : [];
  const cities = (s, country) => Array.isArray(s?.map?.cities?.[country]) ? s.map.cities[country] : [];
  const location = s => s?.player?.location || {};
  const hash = text => Array.from(String(text)).reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 17);
  const round = n => Math.round(n * 10) / 10;
  const seedRand = seed => () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };

  const WORLD_LANDS = [
    {name:"星联", d:"M63 142C80 134 85 112 96 93L121 87C136 66 150 77 169 69L190 53 205 69C228 66 239 92 253 104L267 132C256 144 241 148 243 167L258 181C253 198 240 205 238 225L222 238C228 257 218 268 206 277L196 306 182 327 181 350 166 355 156 334 149 307C130 297 123 284 123 267L102 257C97 241 106 232 97 218L80 212 85 190 72 175C78 160 67 155 63 142Z", islands:"M178 373C191 367 207 378 210 396L207 412 223 429C222 447 213 451 216 469L205 497 196 510C191 494 192 483 184 470L178 451 184 433C171 426 163 412 169 397Z"},
    {name:"法兰西", d:"M331 219C340 200 352 197 363 180L356 165C348 148 368 132 385 127L391 107C410 100 435 107 453 93C471 82 476 61 498 64L512 80C531 74 540 55 559 53C578 49 591 66 611 65L633 54C663 58 668 80 688 85L708 78C731 90 726 116 749 132C764 144 789 149 792 173L777 190C788 208 776 225 788 242C809 253 814 267 802 283L783 291C772 299 786 316 776 330L756 337C751 351 771 366 756 378L735 380C732 397 712 414 695 416L679 398C672 387 663 408 650 420C635 425 618 411 607 396L590 390C589 371 572 362 550 353C543 337 527 340 515 321L487 311C479 294 456 294 442 286L430 301C411 305 400 289 397 272L379 277C365 269 364 250 350 247L336 238C324 232 325 228 331 219Z", islands:"M480 43C486 35 502 34 511 43L506 54 491 59 479 53Z M597 28C605 24 618 30 622 39L613 48 599 44Z M323 183C331 173 338 175 343 185L336 197 326 194Z M316 205 325 200 329 212 322 220 315 216Z"},
    {name:"东瀛", d:"M847 214C850 207 860 203 865 212L863 229C853 235 846 240 847 251L839 267C843 279 833 291 822 303L815 299 817 284 825 268 824 254C837 244 838 237 839 225Z", islands:"M805 309C811 304 817 306 821 314L814 324 802 325 793 338 785 334 791 321Z M864 181C871 175 879 182 882 190L877 202 867 201Z M772 348 781 345 787 352 782 358 772 356Z"},
    {name:"南洋", d:"M646 468C653 455 666 450 677 456L687 462 701 451C715 457 719 471 724 478L709 487 697 485 680 497 667 493 656 488Z", islands:"M740 431C752 417 765 421 775 426L784 440 773 449 756 449 742 442Z M740 506C755 494 768 494 784 501L805 499 824 514 816 529 794 532 780 544 763 538 748 526Z M613 454 623 449 630 458 625 467 614 467Z M702 529 713 524 725 531 719 542 707 540Z M826 462 835 458 841 468 836 477 828 474Z"},
  ];
  const WORLD_POINTS = {
    "星联":{x:171,y:221,dx:0,dy:38}, "法兰西":{x:395,y:242,dx:0,dy:43},
    "北境":{x:558,y:111,dx:0,dy:42}, "华夏":{x:657,y:291,dx:0,dy:45},
    "东瀛":{x:836,y:264,dx:33,dy:22}, "南洋":{x:700,y:476,dx:-9,dy:46},
  };
  const COUNTRY_SHAPES = {
    "华夏":"M154 176C162 146 194 140 221 144L242 121 280 124C297 106 325 110 341 87L372 92C392 115 419 117 441 106L471 93 506 113C531 109 554 125 573 145L606 141 631 125C659 132 670 154 699 156L720 176 754 175C772 191 774 213 798 227L817 249C813 271 795 279 781 294L790 316 815 332C818 351 796 360 783 369L782 398 757 407C744 422 753 442 734 455L713 453C696 466 692 489 673 497L646 483C631 491 620 514 603 511L577 496 552 512 524 505C500 521 480 526 462 511L432 504 410 482C388 484 368 474 355 460L320 464 303 444C278 450 257 437 246 417L219 413C210 393 218 375 200 364L182 348 192 325C175 305 159 293 170 272L181 253C163 233 145 213 154 196Z",
    "法兰西":"M279 121 322 102 365 114 391 87 429 102 460 86 488 111 523 105 550 129 590 132 610 158 651 161 665 192 697 211 685 242 713 267 699 293 718 324 699 348 705 380 677 398 670 430 633 445 612 478 574 472 548 498 511 489 476 511 442 492 405 500 382 477 344 481 323 454 294 446 297 416 270 393 282 362 257 336 274 305 252 279 270 250 251 223 270 195 256 168Z",
    "星联":"M150 146 180 115 214 113 240 85 281 94 304 75 337 95 371 85 402 104 446 98 468 120 511 110 543 137 585 132 610 156 648 150 672 179 709 179 724 211 763 223 748 254 779 277 764 308 780 334 757 359 763 385 733 411 742 441 710 456 694 489 655 483 626 505 592 487 563 506 524 489 487 504 459 481 419 486 388 463 353 470 325 444 288 442 273 412 238 405 233 375 205 362 214 333 185 315 200 284 176 259 184 231 161 209 170 179Z",
    "东瀛":"M652 104 682 91 707 111 705 141 681 167 679 197 651 217 648 247 623 270 622 300 597 328 583 357 559 372 547 401 522 413 502 446 474 453 455 481 427 485 410 467 419 439 445 423 455 394 481 378 489 350 514 337 518 306 544 289 550 257 575 239 579 210 606 192 608 162 638 145Z M373 472 399 464 415 481 408 503 385 515 369 505 347 518 331 503 345 486Z M702 69 725 64 746 84 735 106 710 103Z",
    "南洋":"M302 350 338 327 375 335 403 319 434 336 465 331 483 357 508 363 515 392 494 413 468 416 448 436 414 427 392 447 358 434 329 439 316 416 291 400 299 376Z M569 186 595 161 629 168 650 151 681 168 713 164 734 185 762 197 752 224 766 245 745 270 715 270 693 292 663 280 635 289 618 267 588 263 587 235 566 218Z M569 471 599 454 626 463 652 451 682 469 705 465 726 484 713 507 686 511 666 533 639 523 615 534 596 515 571 512 558 492Z M229 314 246 306 263 317 259 337 242 344 226 334Z M782 357 807 350 828 370 814 394 790 392Z",
    "北境":"M196 120 222 101 251 113 280 90 314 105 342 84 372 101 406 91 435 111 470 97 502 115 534 99 565 118 603 105 634 130 669 124 694 147 730 150 744 182 777 197 767 226 796 248 781 275 803 302 783 325 789 354 762 376 761 408 727 424 709 456 674 450 642 480 608 470 574 492 542 477 509 497 474 482 439 491 414 469 375 471 351 447 317 450 295 425 263 420 252 391 220 376 228 344 202 321 215 289 190 268 206 238 184 216 202 187 183 160Z",
  };

  function definitions(id) {
    return `<defs>
      <pattern id="${id}-grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" class="ca-grid-line"/></pattern>
      <symbol id="${id}-campus" viewBox="-12 -12 24 24"><path d="M-10-3 0-9 10-3M-8-1v9M-3-1v9M3-1v9M8-1v9M-11 9h22M-9-1H9"/></symbol>
      <symbol id="${id}-city" viewBox="-12 -12 24 24"><path d="M-9 10V-3h8v13M-1 10V-10H9v20M-6 0v2m0 3v2M2-6h4M2-2h4M2 2h4M2 6h4"/></symbol>
      <symbol id="${id}-culture" viewBox="-12 -12 24 24"><path d="M-10-4 0-10 10-4M-9-2H9M-7-2v10M0-2v10M7-2v10M-10 9h20"/></symbol>
      <symbol id="${id}-leisure" viewBox="-12 -12 24 24"><path d="M-2 5V-8l11-2v12M-2-4l11-2"/><ellipse cx="-5" cy="6" rx="4" ry="3"/><ellipse cx="6" cy="3" rx="4" ry="3"/></symbol>
      <symbol id="${id}-transport" viewBox="-12 -12 24 24"><rect x="-8" y="-10" width="16" height="17" rx="4"/><path d="M-8-3H8M-4 7l-3 4M4 7l3 4M-4 2h1m6 0h1"/></symbol>
      <symbol id="${id}-nature" viewBox="-12 -12 24 24"><path d="M0-11-7-2h3l-6 8H10L4-2h3ZM0 6v5"/></symbol>
      <symbol id="${id}-secret" viewBox="-12 -12 24 24"><path d="m-9-1 14-7 4 7-14 7ZM-1 4l-5 7M0 4l5 7"/></symbol>
    </defs>`;
  }

  // Keep fictional geography deterministic; round individual coastline corners,
  // rather than making the whole country a repeated scalloped outline.
  function smoothCoast(path) {
    if (/[CcQqAaHhVvSsTt]/.test(path)) return path;
    return String(path).split(/(?=M)/).map(part => {
      const values = part.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
      const pts = [];
      for (let i = 0; i + 1 < values.length; i += 2) pts.push([values[i], values[i + 1]]);
      if (pts.length < 3) return part;
      let result = `M${pts[0][0]} ${pts[0][1]}`;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[(i - 1 + pts.length) % pts.length], b = pts[i];
        const c = pts[(i + 1) % pts.length], d = pts[(i + 2) % pts.length];
        result += `C${round(b[0] + (c[0] - a[0]) * .13)} ${round(b[1] + (c[1] - a[1]) * .13)} ${round(c[0] - (d[0] - b[0]) * .13)} ${round(c[1] - (d[1] - b[1]) * .13)} ${c[0]} ${c[1]}`;
      }
      return result + "Z";
    }).join(" ");
  }
  function sheet(id, title, subtitle, body, opts = {}) {
    const compact = !!opts.compact;
    const controls = compact ? "" : `<div class="ca-map-controls" data-atlas-control="tools" role="group" aria-label="地图视角"><button type="button" data-map-action="in" aria-label="放大地图" title="放大地图">＋</button><button type="button" data-map-action="out" aria-label="缩小地图" title="缩小地图">−</button><button type="button" data-map-action="reset" aria-label="恢复地图视角" title="恢复地图视角">100%</button><details class="ca-pan-menu"><summary aria-label="平移地图" title="平移地图">移动</summary><div><button type="button" data-map-action="north" aria-label="地图向北移动">↑</button><button type="button" data-map-action="west" aria-label="地图向西移动">←</button><button type="button" data-map-action="east" aria-label="地图向东移动">→</button><button type="button" data-map-action="south" aria-label="地图向南移动">↓</button></div></details></div>`;
    const legend = opts.level === "city" ? `<span><i class="ca-legend-road"></i>主干道</span><span><i class="ca-legend-transit"></i>城市轨道</span><span><i class="ca-legend-park"></i>绿地</span>` : `<span><i class="ca-legend-road"></i>城际交通</span><span><i class="ca-legend-water"></i>水系</span><span><i class="ca-legend-park"></i>地形</span>`;
    return `<div class="ca-map ca-electronic${compact ? " ca-compact" : ""}" data-map-level="${esc(opts.level || "city")}"><svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" class="atlas-svg cartography${compact ? " compact" : ""}" role="group" aria-label="${esc(title)}" data-ca-base="0 0 ${W} ${H}" data-ca-zoom="1">
      <title>${esc(title)}</title><desc>${esc(subtitle)}。架空世界地理示意，非现实导航。可用地图按钮缩放、移动，或拖动底图。</desc>${definitions(id)}
      <rect width="960" height="620" class="ca-ocean"/><rect width="960" height="620" fill="url(#${id}-grid)" class="ca-reference-grid"/>
      <defs><clipPath id="${id}-extent"><rect width="960" height="620"/></clipPath></defs><g clip-path="url(#${id}-extent)">${body}</g>
    </svg>${compact ? "" : `<div class="ca-map-heading"><b>${esc(title)}</b><span>${esc(subtitle)}</span></div><div class="ca-north" aria-hidden="true"><span>N</span><svg viewBox="0 0 24 30"><path d="M12 2 20 26 12 21 4 26Z"/></svg></div><div class="ca-map-legend" aria-hidden="true">${legend}</div><div class="ca-map-caption">架空地理示意 · 选择地点查看实际行程</div>`}${controls}</div>`;
  }
  function flight(a, b, bend = -70) {
    return `<path class="ca-flight" d="M${a.x} ${a.y}Q${round((a.x + b.x) / 2)} ${round((a.y + b.y) / 2 + bend)} ${b.x} ${b.y}"/>`;
  }
  function visibleList(state, visiblePlaces) {
    return Array.isArray(visiblePlaces) ? visiblePlaces : list(state);
  }
  function countryMarker(name, position, current, count, matches) {
    const {x, y, dx = 0, dy = 32} = position;
    return `<g class="mcountry ca-country-pin${current ? " current" : ""}" data-country="${esc(name)}" role="button" tabindex="0" aria-label="${esc(name)}${current ? "，当前所在" : "，查看城市"}" transform="translate(${x} ${y})"><title>${esc(name)} · ${count}座城市 · ${matches}个去处</title><circle r="25" class="ca-marker-hit"/><circle r="8" class="ca-country-halo"/><circle r="3" class="ca-country-center"/><g transform="translate(${dx} ${Math.min(dy, 32)})"><text text-anchor="middle" class="ca-country-title">${esc(name)}</text><text text-anchor="middle" y="17" class="ca-country-subtitle">${count}座城市 · ${matches}个去处</text></g></g>`;
  }
  function world(state, visiblePlaces = null) {
    const id = "ca-world", loc = location(state), matches = visibleList(state, visiblePlaces);
    const allowed = c => matches.filter(p => p.country === c || cities(state,c).some(city => city.name === p.city));
    const available = countries(state).filter(c => visiblePlaces === null || allowed(c.name).length);
    const land = WORLD_LANDS.map((region, i) => {
      const whole = smoothCoast(region.d + " " + (region.islands || ""));
      const p = WORLD_POINTS[region.name];
      const valleys = `<path d="M${p.x-57} ${p.y-50}Q${p.x-25} ${p.y-95} ${p.x+16} ${p.y-48}T${p.x+63} ${p.y-8}L${p.x+13} ${p.y+26}Q${p.x-49} ${p.y+19} ${p.x-57} ${p.y-50}Z" class="ca-terrain-band"/><path d="M${p.x-24} ${p.y-40}Q${p.x+20} ${p.y-15} ${p.x+12} ${p.y+42}T${p.x+46} ${p.y+87}" class="ca-world-river"/>`;
      const districts = region.name === "法兰西"
        ? `<path class="ca-admin-border" d="M493 75Q510 156 493 192T543 252M493 192Q564 203 600 224T703 217L787 240"/><path class="ca-terrain-band" d="M468 109Q521 71 581 97T645 163L601 188 554 161 507 165Z M565 276Q603 241 652 261L693 321 672 363 624 341Z"/><path class="ca-world-river" d="M546 131Q572 166 590 194T645 273L685 303M574 288Q620 306 655 331T731 365"/>`
        : `<path class="ca-admin-border" d="M${p.x-100} ${p.y-19}Q${p.x-5} ${p.y-10} ${p.x+80} ${p.y+35}M${p.x-35} ${p.y-95}Q${p.x+8} ${p.y-4} ${p.x-18} ${p.y+92}"/>`;
      return `<g class="ca-country-land ca-land-${i}" aria-hidden="true"><path d="${whole}" class="ca-land"/><clipPath id="${id}-${i}"><path d="${whole}"/></clipPath><g clip-path="url(#${id}-${i})">${valleys}${districts}</g></g>`;
    }).join("");
    const routes = [["星联","华夏",-112],["华夏","法兰西",-78],["华夏","东瀛",-42],["华夏","南洋",43],["北境","法兰西",-50]].map(([a,b,bend]) => flight(WORLD_POINTS[a],WORLD_POINTS[b],bend)).join("");
    const labels = `<g class="ca-water-labels" aria-hidden="true"><text x="318" y="389">长风洋</text><text x="875" y="444">东海</text><text x="511" y="545">南境洋</text><text x="266" y="81" class="ca-water-small">北方海域</text></g>`;
    const pins = available.map((c,i) => countryMarker(c.name,WORLD_POINTS[c.name] || {x:100+i*125,y:310},c.name===loc.country,new Set(allowed(c.name).map(p=>p.city)).size,allowed(c.name).length)).join("");
    return sheet(id,"世界地图",`${available.length}个国家 · ${new Set(matches.map(p=>p.city)).size}座城市 · ${matches.length}个去处`,land+routes+labels+pins,{level:"world"});
  }
  const COUNTRY_RIVERS = {
    "华夏":"M340 112C414 197 337 224 449 275S594 307 624 365 718 386 790 415",
    "法兰西":"M365 128C469 186 387 252 507 293S590 374 659 440",
    "星联":"M325 114C404 208 342 260 467 305S580 386 695 436",
    "北境":"M347 141C442 216 369 266 499 312S585 401 688 441",
  };
  function countryPoint(country, city) {
    const x = clamp(city.x ?? 50,0,100), y = clamp(city.y ?? 50,0,100);
    if(country==="东瀛") return {x:x>48?622:463,y:y<50?244:421};
    if(country==="南洋") return {x:y>45?411:669,y:y>45?384:225};
    return {x:150+x*6.7,y:103+y*4.25};
  }
  function cityMarker(name,p,current,id,count) {
    return `<g class="mcity ca-city-pin${current?" current":""}" data-city="${esc(name)}" role="button" tabindex="0" aria-label="${esc(name)}${current?"，当前所在":"，查看地点"}" transform="translate(${round(p.x)} ${round(p.y)})"><title>${esc(name)} · ${count}个去处</title><circle r="26" class="ca-marker-hit"/><circle r="7" class="ca-city-marker"/><circle r="2.5" class="ca-city-marker-center"/><text x="14" y="5" class="ca-city-title">${esc(name)}</text><text x="14" y="21" class="ca-city-subtitle">${count}个去处</text></g>`;
  }
  function country(state,name,visiblePlaces = null) {
    const id="ca-country-"+hash(name),loc=location(state),shape=smoothCoast(COUNTRY_SHAPES[name]||COUNTRY_SHAPES["华夏"]);
    const points=cities(state,name).map(c=>({...c,...countryPoint(name,c)}));
    const matching=visibleList(state,visiblePlaces).filter(p=>p.country===name||points.some(c=>c.name===p.city));
    const roads=points.slice(1).map((c,i)=>{
      const a=points[i],cx=round((a.x+c.x)/2+24),cy=round((a.y+c.y)/2-24);
      const d=`M${round(a.x)} ${round(a.y)}Q${cx} ${cy} ${round(c.x)} ${round(c.y)}`;
      const rail=`M${round(a.x+9)} ${round(a.y+8)}Q${cx+23} ${cy+17} ${round(c.x+9)} ${round(c.y+8)}`;
      return `<path d="${d}" class="ca-road-edge"/><path d="${d}" class="ca-highway"/><path d="${rail}" class="ca-country-rail"/><g class="ca-road-shield" transform="translate(${cx} ${cy})"><rect x="-14" y="-7" width="28" height="14" rx="3"/><text text-anchor="middle" y="3.5">G${i+1}</text></g>`;
    }).join("");
    const borders=`<path class="ca-admin-border" d="M220 142Q367 242 424 265T738 306M294 437Q439 354 424 265T490 103M424 265Q560 370 627 491M181 296Q327 330 424 265"/>`;
    const river=COUNTRY_RIVERS[name]||"";
    const riverLines=river?`<path d="${river}" class="ca-river"/><path d="M251 263Q323 270 390 252M470 197Q500 251 524 300M548 433Q607 412 624 365" class="ca-river-tributary"/>`:"";
    const terrain=`<path d="M154 148Q292 92 395 151T430 325Q343 384 242 351T154 148Z" class="ca-terrain-band"/><path d="M574 159Q650 115 746 180T704 358Q639 405 571 322T574 159Z" class="ca-forest-area"/><path d="M332 401Q440 345 526 410T507 523L359 518Z" class="ca-forest-area"/>`;
    const ground=`<path d="${shape}" class="ca-land"/><clipPath id="${id}-land"><path d="${shape}"/></clipPath><g clip-path="url(#${id}-land)">${terrain}${borders}${riverLines}${roads}</g>`;
    const labels=`<g class="ca-region-labels" aria-hidden="true"><text x="294" y="205">${name==="北境"?"冰脊高原":"西岭地区"}</text><text x="586" y="451">${name==="南洋"?"南部群岛":"南部平原"}</text><text x="661" y="212">北部林区</text></g><g class="ca-water-labels" aria-hidden="true"><text x="849" y="399">${name==="星联"?"长风洋":name==="北境"?"浮冰海":"远航海"}</text></g>`;
    const shown=points.filter(c=>visiblePlaces===null||matching.some(p=>p.city===c.name));
    const pins=shown.map(c=>cityMarker(c.name,c,c.name===loc.city,id,matching.filter(p=>p.city===c.name).length)).join("");
    return sheet(id,`${name}地图`,`${shown.length}座城市 · ${matching.length}个去处 · 城际交通`,ground+labels+pins,{level:"country"});
  }

  function overlap(a,b,pad=3) { return a.x < b.x+b.w+pad && a.x+a.w+pad > b.x && a.y < b.y+b.h+pad && a.y+a.h+pad > b.y; }
  function labelWidth(name) { return Math.min(200,Array.from(String(name)).reduce((n,c)=>n+(/\p{Script=Han}/u.test(c)?14.5:8.2),0)+17); }
  function placeLayout(places) {
    const pins = [], labels = [];
    places.forEach((p,i)=> {
      const target={x:102+clamp(p.x ?? (16+(i%5)*17),0,100)*7.55,y:112+clamp(p.y ?? (14+Math.floor(i/5)*23),0,100)*4.12};
      const w=labelWidth(p.name), h=25;
      const offsets=[{x:0,y:0}];
      for (const r of [36,67,100,138]) for(let n=0;n<12;n++) offsets.push({x:Math.cos(n*Math.PI/6)*r,y:Math.sin(n*Math.PI/6)*r*.68});
      let chosen=null;
      for(const delta of offsets) {
        const point={x:round(clamp(target.x+delta.x,80,872)),y:round(clamp(target.y+delta.y,123,520))};
        if(pins.some(a=>Math.hypot(point.x-a.x,point.y-a.y)<49)||labels.some(b=>overlap({x:point.x-19,y:point.y-19,w:38,h:38},b,2)))continue;
        const candidates=[{x:point.x+19,y:point.y-13},{x:point.x-w-19,y:point.y-13},{x:point.x-w/2,y:point.y+21},{x:point.x-w/2,y:point.y-47}];
        const box=candidates.map(c=>({...c,w,h})).find(b=>b.x>37&&b.x+b.w<921&&b.y>101&&b.y+b.h<552&&!labels.some(l=>overlap(b,l,6))&&!pins.some(a=>overlap(b,{x:a.x-18,y:a.y-18,w:36,h:36},1)));
        if(box){chosen={...p,...point,box};break;}
      }
      if(!chosen) { const x=85+(i%5)*174,y=143+Math.floor(i/5)*92; chosen={...p,x,y,box:{x:x+21,y:y-13,w,h}}; }
      pins.push(chosen);labels.push(chosen.box);
    });
    return pins;
  }
  function cityBase(id,name,places) {
    const seed=hash(name),random=seedRand(seed),coastal=/魔都|江海|海湾|蔚蓝|新港|星湾|狮城|椰湾|松港/.test(name);
    const variant=seed%3, phase=seed%13;
    const xs=[-80,25,97,163,234,325,405,461,538,620,714,805,910,1040];
    const ys=[-70,24,101,156,222,298,358,433,507,591,690];
    // An old central street network bends into newer, broader neighbourhoods.
    const node=(x,y)=>({x:x+31*Math.sin(y/138+phase)+14*Math.sin(x/175+y/99),y:y+25*Math.sin(x/183+phase)+17*Math.cos(y/167+x/112)});
    const point=p=>`${round(p.x)} ${round(p.y)}`;
    const curve=pts=>`M${point(pts[0])}`+pts.slice(1).map((p,i)=>{
      const a=pts[Math.max(0,i-1)],b=pts[i],c=p,d=pts[Math.min(pts.length-1,i+2)];
      return `C${point({x:b.x+(c.x-a.x)/6,y:b.y+(c.y-a.y)/6})} ${point({x:c.x-(d.x-b.x)/6,y:c.y-(d.y-b.y)/6})} ${point(c)}`;
    }).join('');
    const polygon=pts=>`M${pts.map(point).join('L')}Z`;
    const riverX=y=>(coastal?760:668)+35*Math.sin(y/137+phase)+46*Math.sin(y/243+1.3);
    const riverPoints=Array.from({length:18},(_,i)=>({y:-80+i*46})).map(p=>({...p,x:riverX(p.y)}));
    const river=polygon([...riverPoints.map(p=>({x:p.x-17-4*Math.sin(p.y/65),y:p.y})),...riverPoints.slice().reverse().map(p=>({x:p.x+18+5*Math.cos(p.y/83),y:p.y}))]);
    const blocks=[];
    for(let r=0;r<ys.length-1;r++)for(let c=0;c<xs.length-1;c++){
      const x=xs[c],y=ys[r],w=xs[c+1]-x,h=ys[r+1]-y;
      const middle=node(x+w/2,y+h/2);
      if(Math.abs(middle.x-riverX(middle.y))<50||(coastal&&middle.x>893))continue;
      const zone=(r*7+c+variant)%19===0?'park':(c+r+variant)%9===0?'civic':c>6&&r>5?'business':'residential';
      const cell=(u,v)=>node(x+u*w,y+v*h);
      blocks.push(`<path d="${polygon([cell(.10,.12),cell(.89,.09),cell(.91,.88),cell(.09,.91)])}" class="ca-use-${zone}"/>`);
      if(zone==='park'){
        blocks.push(`<path d="${curve([cell(.12,.6),cell(.4,.35),cell(.66,.68),cell(.9,.42)])}" class="ca-park-path"/>`);
        continue;
      }
      const columns=w>85?4:3,rows=h>70?3:2;
      for(let j=0;j<rows;j++)for(let k=0;k<columns;k++){
        if(random()<.18)continue;
        const u=.15+k*.7/columns+random()*.025,v=.16+j*.68/rows+random()*.025;
        const du=(.45+random()*.2)/columns,dv=(.38+random()*.25)/rows;
        blocks.push(`<path d="${polygon([cell(u,v),cell(u+du,v),cell(u+du,v+dv),cell(u,v+dv)])}" class="ca-building"/>`);
      }
    }
    const network=[];
    ys.slice(1,-1).forEach((y,i)=>network.push({d:curve(xs.map(x=>node(x,y))),major:i===2||i===6}));
    xs.slice(1,-1).forEach((x,i)=>{
      const pts=ys.map(y=>node(x,y));
      network.push({d:curve(pts),major:i===3||i===8});
    });
    // Short alleys and crescents break the street blocks instead of repeating a checkerboard.
    for(let i=0;i<17;i++){
      const x=40+random()*530,y=60+random()*480;
      network.push({d:curve([node(x,y),node(x+22,y-14),node(x+54,y-8)]),alley:true});
    }
    const road=(d,major=false)=>`<path d="${d}" class="${major?'ca-arterial-edge':'ca-local-road-edge'}"/><path d="${d}" class="${major?'ca-arterial':'ca-local-road'}"/>`;
    const roads=network.map(r=>`<g${r.alley?' class="ca-alley"':''}>${road(r.d,r.major)}</g>`).join('');
    const express=variant===0?'M-45 515C168 552 216 412 351 395S638 482 727 359 872 218 1002 204':variant===1?'M-35 357C130 230 209 269 336 207S548 89 724 122 879 72 1005 34':'M-45 425C176 479 250 372 373 326S584 153 725 196 854 168 1010 98';
    const ring='M150 169C227 68 479 53 571 161S631 428 503 490 208 510 133 398 74 263 150 169';
    const bridges=[156,358,507].map(y=>{
      const x=riverX(y);return `<g class="ca-bridge">${road(`M${round(x-41)} ${y-3}Q${round(x)} ${y+3} ${round(x+41)} ${y+7}`,true)}</g>`;
    }).join('');
    const metro='M91 606C117 475 136 388 239 378S423 418 536 354 722 386 787 272 825 167 852 74';
    const stationPoints=[[112,493],[166,403],[284,380],[459,389],[649,362],[789,267]];
    const stations=stationPoints.map(([x,y],i)=>`<g class="ca-transit-station" transform="translate(${x} ${y})"><circle r="3.5"/><text x="7" y="-6">${['西城','文苑','中央广场','东街','滨河','新城'][i]}站</text></g>`).join('');
    const rail='M-30 587C213 534 325 614 487 549S748 492 999 516';
    const names=name==='京都'?['文教区','西城','东城','新城商务区']:coastal?['老城区','中央商务区','滨江区','临港新区']:['北城区','老城中心','河东区','科创园区'];
    const labels=`<g class="ca-district-labels"><text x="211" y="111">${names[0]}</text><text x="288" y="306">${names[1]}</text><text x="804" y="315">${names[2]}</text><text x="463" y="548">${names[3]}</text></g><g class="ca-street-labels"><text x="326" y="221" transform="rotate(-12 326 221)">${name==='京都'?'银杏大道':'中央大道'}</text><text x="440" y="477" transform="rotate(-14 440 477)">人民路</text><text x="173" y="272" transform="rotate(79 173 272)">中山路</text></g><g class="ca-road-shield" transform="translate(380 199)"><rect x="-16" y="-8" width="32" height="16" rx="3"/><text y="4" text-anchor="middle">S${seed%9+1}</text></g><text class="ca-river-name" transform="translate(${round(riverX(170))} 165) rotate(83)">${coastal?'滨江':'清溪河'}</text>`;
    const footprints=places.filter(p=>['campus','nature'].includes(p.type)).map(p=>`<path d="M${p.x-28} ${p.y-19}q24-16 59-6l8 37q-26 17-64 6Z" class="${p.type==='nature'?'ca-park-footprint':'ca-campus-footprint'}"/>`).join('');
    // Older streets grew around irregular plots; the east bank keeps planned avenues.
    const sites=[];
    for(let attempt=0;attempt<400&&sites.length<86;attempt++){
      const p={x:-30+random()*580,y:-30+random()*690};
      if(sites.every(q=>Math.hypot(p.x-q.x,p.y-q.y)>29+Math.abs(p.x-230)/17))sites.push(p);
    }
    const cells=sites.map((site,i)=>{
      let poly=[{x:-70,y:-70},{x:590,y:-70},{x:590,y:700},{x:-70,y:700}];
      for(const other of sites){
        if(site===other)continue;
        const nx=other.x-site.x,ny=other.y-site.y,edge=(other.x**2+other.y**2-site.x**2-site.y**2)/2,next=[];
        for(let j=0;j<poly.length;j++){
          const a=poly[j],b=poly[(j+1)%poly.length],da=a.x*nx+a.y*ny-edge,db=b.x*nx+b.y*ny-edge;
          if(da<=0)next.push(a);
          if((da<=0)!==(db<=0)){const t=da/(da-db);next.push({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});}
        }
        poly=next;if(!poly.length)break;
      }
      if(poly.length<3)return '';
      const inset=(p,t)=>({x:p.x+(site.x-p.x)*t,y:p.y+(site.y-p.y)*t}),plot=poly.map(p=>inset(p,.12)),buildings=[];
      if(i%19!==0)for(let j=0;j<plot.length;j++){
        const a=plot[j],b=plot[(j+1)%plot.length],parts=Math.max(1,Math.floor(Math.hypot(b.x-a.x,b.y-a.y)/22));
        for(let k=0;k<parts;k++){
          if(random()<.15)continue;
          const along=t=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t}),u=along((k+.12)/parts),v=along((k+.83)/parts);
          buildings.push(`<path d="${polygon([u,v,inset(v,.35),inset(u,.35)])}" class="ca-building"/>`);
        }
      }
      return `<path d="${polygon(plot)}" class="ca-use-${i%19===0?'park':i%7===0?'civic':'residential'}"/>${buildings.join('')}<path d="${polygon(poly)}" class="ca-old-street"/>`;
    }).join('');
    const oldTown=`<defs><clipPath id="${id}-old-town"><path d="M-50-20H306C392 22 359 126 426 177S488 272 447 340 508 464 414 535 306 668-50 658Z"/></clipPath></defs><g clip-path="url(#${id}-old-town)" class="ca-old-town"><rect x="-70" y="-70" width="660" height="770" class="ca-city-ground"/>${cells}${footprints}</g>`;
    const coast=coastal?'<path d="M930-30C862 75 936 124 906 223S865 339 907 420 855 525 908 660H1000V-30Z" class="ca-coastal-water"/>':'';
    return `<g class="ca-city-basemap" data-city-variant="${variant}" aria-hidden="true"><rect width="960" height="620" class="ca-city-ground"/><g class="ca-landuse">${blocks.join('')}${footprints}</g>${roads}${oldTown}<path d="${ring}" class="ca-ring-road-edge"/><path d="${ring}" class="ca-ring-road"/><path d="${express}" class="ca-express-edge"/><path d="${express}" class="ca-express"/><path d="${river}" class="ca-city-water"/>${coast}${bridges}<path d="${rail}" class="ca-city-rail-edge"/><path d="${rail}" class="ca-city-rail"/><g class="ca-transit"><path d="${metro}" class="ca-transit-casing"/><path d="${metro}" class="ca-transit-line"/>${stations}</g>${labels}</g>`;
  }
  function placeMarker(p,current,id,compact) {
    const type=["campus","city","culture","leisure","transport","nature","secret"].includes(p.type)?p.type:"city",box=p.box;
    const label=compact?(current?`<text x="${p.x}" y="${p.y+42}" text-anchor="middle" class="ca-mini-label">${esc(p.name)}</text>`:""):`<g class="ca-place-label"><rect x="${round(box.x)}" y="${round(box.y)}" width="${round(box.w)}" height="${box.h}" rx="3" class="ca-label-paper" data-map-label-box="${[box.x,box.y,box.w,box.h].map(round).join(',')}"/><text x="${round(box.x+8)}" y="${round(box.y+17.5)}">${esc(p.name)}</text></g>`;
    return `<g class="mplace ca-place-pin ca-type-${type}${current?" current":""}${p.discovered?" visited":""}" data-place="${esc(p.name)}" data-city="${esc(p.city)}" data-map-point="${p.x},${p.y}" role="button" tabindex="0" aria-label="${esc(p.name)}${current?"，当前所在":"，查看详情"}"><title>${esc(p.name)}${current?" · 当前所在":""}</title><circle cx="${p.x}" cy="${p.y}" r="25" class="ca-marker-hit"/>${current?`<circle cx="${p.x}" cy="${p.y}" r="22" class="ca-current-ring"/>`:""}<circle cx="${p.x}" cy="${p.y}" r="13" class="ca-place-symbol-bg"/><use href="#${id}-${type}" x="${p.x-8}" y="${p.y-8}" width="16" height="16" class="ca-place-symbol"/>${label}</g>`;
  }
  function city(state,name,compact=false,typeFilter="",visiblePlaces=null) {
    const id="ca-city-"+hash(name)+(compact?"-mini":""),loc=location(state);
    // Layout belongs to the complete city, not the current filter result.
    const complete=placeLayout(list(state).filter(p=>p.city===name));
    const allowed=Array.isArray(visiblePlaces)?new Set(visiblePlaces.map(p=>p.name)):null;
    const places=complete.filter(p=>compact||((!typeFilter||p.type===typeFilter)&&(!allowed||allowed.has(p.name))));
    const pins=places.map(p=>placeMarker(p,p.name===loc.place,id,compact)).join("");
    return sheet(id,`${name}地图`,`${places.length}个去处 · 街道与公共交通`,cityBase(id,name,complete)+pins,{level:"city",compact});
  }

  function highlight(root,placeName) {
    const svg=root?.querySelector?.("svg.cartography");if(!svg)return;
    const pins=Array.from(svg.querySelectorAll(".ca-place-pin"));
    let selected=null,origin=null;
    for(const pin of pins){const picked=pin.dataset.place===placeName;pin.classList.toggle("selected",picked);pin.setAttribute("aria-pressed",String(picked));if(picked)selected=pin;if(pin.classList.contains("current"))origin=pin;}
    svg.querySelector(".ca-selected-route")?.remove();
    if(!origin||!selected||origin===selected)return;
    const a=origin.dataset.mapPoint.split(",").map(Number),b=selected.dataset.mapPoint.split(",").map(Number);
    if([...a,...b].some(n=>!Number.isFinite(n)))return;
    const group=svg.ownerDocument.createElementNS("http://www.w3.org/2000/svg","g");
    group.setAttribute("class","ca-selected-route");group.setAttribute("aria-hidden","true");
    const d=`M${a[0]} ${a[1]}Q${round((a[0]+b[0])/2+25)} ${round((a[1]+b[1])/2-24)} ${b[0]} ${b[1]}`;
    for(const cls of ["ca-selected-route-edge","ca-selected-route-line"]){const path=svg.ownerDocument.createElementNS("http://www.w3.org/2000/svg","path");path.setAttribute("d",d);path.setAttribute("class",cls);group.appendChild(path);}
    pins[0].parentNode.insertBefore(group,pins[0]);
  }

  const mounted=new WeakSet();
  function mount(root) {
    root=root||(typeof document!=="undefined"?document:null);
    if(!root||mounted.has(root)||typeof root.addEventListener!=="function")return;
    mounted.add(root);
    const state=new WeakMap();
    const read=svg=>{
      if(!state.has(svg)){const base=(svg.getAttribute("data-ca-base")||"0 0 960 620").split(" ").map(Number);state.set(svg,{base,box:base.slice(),zoom:1});}
      return state.get(svg);
    };
    const write=(svg,s)=>{
      const [bx,by,bw,bh]=s.base;
      s.box[0]=clamp(s.box[0],bx-bw*.15,bx+bw-s.box[2]+bw*.15);
      s.box[1]=clamp(s.box[1],by-bh*.15,by+bh-s.box[3]+bh*.15);
      svg.setAttribute("viewBox",s.box.map(round).join(" "));
      svg.setAttribute("data-ca-zoom",String(round(s.zoom)));
      const reset=svg.closest(".ca-map")?.querySelector('[data-map-action="reset"]');
      if(reset)reset.textContent=Math.round(s.zoom*100)+"%";
    };
    let drag=null,swallowUntil=0;
    root.addEventListener("click",event=>{
      if(Date.now()<swallowUntil&&event.target.closest?.(".ca-map")){event.preventDefault();event.stopPropagation();return;}
      const btn=event.target.closest?.("[data-map-action]");if(!btn)return;
      const svg=btn.closest(".ca-map")?.querySelector("svg.cartography");if(!svg)return;
      event.preventDefault();event.stopPropagation();
      const s=read(svg),action=btn.dataset.mapAction;
      if(action==="reset"){s.zoom=1;s.box=s.base.slice();}
      else if(action==="in"||action==="out"){
        const zoom=clamp(s.zoom*(action==="in"?1.4:1/1.4),1,4.5),ratio=s.zoom/zoom;
        const nw=s.box[2]*ratio,nh=s.box[3]*ratio;
        s.box=[s.box[0]+(s.box[2]-nw)/2,s.box[1]+(s.box[3]-nh)/2,nw,nh];s.zoom=zoom;
      }else{
        if(action==="west")s.box[0]-=s.box[2]*.22;if(action==="east")s.box[0]+=s.box[2]*.22;
        if(action==="north")s.box[1]-=s.box[3]*.22;if(action==="south")s.box[1]+=s.box[3]*.22;
      }
      write(svg,s);
    },true);
    root.addEventListener("pointerdown",event=>{
      const svg=event.target.closest?.("svg.cartography");
      if(!svg||svg.closest(".ca-compact")||event.target.closest?.("[role=button],button,summary")||event.button>0)return;
      const s=read(svg);drag={svg,s,point:[event.clientX,event.clientY],box:s.box.slice(),moved:false,pointerId:event.pointerId};
    });
    root.addEventListener("pointermove",event=>{
      if(!drag||drag.pointerId!==event.pointerId)return;
      const dx=event.clientX-drag.point[0],dy=event.clientY-drag.point[1];
      if(Math.abs(dx)+Math.abs(dy)<5&&!drag.moved)return;
      drag.moved=true;const rect=drag.svg.getBoundingClientRect();
      if(!rect.width||!rect.height)return;
      event.preventDefault();drag.svg.classList.add("ca-dragging");
      drag.svg.setPointerCapture?.(event.pointerId);
      drag.s.box[0]=drag.box[0]-dx/rect.width*drag.box[2];drag.s.box[1]=drag.box[1]-dy/rect.height*drag.box[3];write(drag.svg,drag.s);
    },{passive:false});
    const stop=()=>{if(drag){drag.svg.classList.remove("ca-dragging");if(drag.moved)swallowUntil=Date.now()+220;}drag=null;};
    root.addEventListener("pointerup",stop);root.addEventListener("pointercancel",stop);
  }
  scope.CityAtlas=Object.freeze({world,country,city,mount,highlight});
})(typeof window!=="undefined"?window:globalThis);
