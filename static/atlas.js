/* An illustrated travel atlas. Geometry is local, deterministic and independent of the save. */
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
    {name:"星联", d:"M68 126 91 110 100 82 133 68 157 76 179 62 206 75 222 96 249 103 265 130 249 150 255 177 281 189 270 216 251 230 247 261 224 280 217 309 190 323 182 354 158 349 148 322 125 306 120 280 99 265 94 237 73 224 81 197 63 181 75 158Z", islands:"M178 377 194 367 211 384 214 407 229 423 218 441 224 460 213 487 197 506 192 482 177 465 182 442 165 424 169 400Z"},
    {name:"法兰西", d:"M349 200 365 182 387 187 397 173 416 186 432 182 441 203 462 209 452 226 461 245 444 253 443 275 420 279 411 297 390 290 382 307 361 294 357 269 339 253 347 230 334 218Z", islands:"M324 183 334 172 342 183 334 195Z M317 202 324 196 330 210 322 217Z"},
    {name:"北境", d:"M440 91 456 78 476 86 489 68 518 76 532 58 550 70 566 65 584 79 609 73 624 89 651 82 669 103 695 106 686 128 665 131 654 149 626 143 611 157 589 148 565 158 544 143 519 153 498 137 471 140 460 121 439 113Z", islands:"M479 49 492 38 511 45 506 57 490 61Z M577 38 596 30 612 39 607 53 590 52Z M654 57 667 53 678 67 667 76Z"},
    {name:"华夏", d:"M552 207 575 195 599 201 617 181 645 187 667 181 684 198 710 196 722 212 745 214 751 235 778 247 767 266 785 283 771 304 779 325 758 341 757 365 734 369 720 390 694 385 682 407 660 397 644 413 620 398 600 402 589 381 566 375 566 353 544 339 550 316 533 299 543 276 526 258 541 238 538 219Z", islands:"M752 398 763 390 774 400 770 417 759 422Z M790 353 802 344 811 358 802 373 793 368Z"},
    {name:"东瀛", d:"M846 213 857 203 867 213 864 230 850 244 850 261 837 270 839 290 824 307 814 302 813 287 823 270 822 251 838 237Z", islands:"M805 309 818 305 822 316 811 327 799 326 794 339 784 335 790 321Z M862 179 875 177 885 191 879 205 866 203Z M773 348 783 345 790 352 782 360 772 356Z"},
    {name:"南洋", d:"M643 465 661 451 684 457 701 449 716 460 724 477 711 488 692 488 680 499 661 492 650 481Z", islands:"M738 428 754 417 775 424 787 440 775 451 755 451 740 440Z M740 505 763 493 786 502 806 499 825 514 816 530 793 534 781 546 760 538 743 523Z M611 453 622 448 632 457 626 468 613 468Z M700 528 713 522 727 530 720 543 707 541Z M824 461 835 457 844 467 837 478 827 475Z"},
  ];
  const WORLD_POINTS = {
    "星联":{x:171,y:221,dx:0,dy:38}, "法兰西":{x:395,y:242,dx:0,dy:43},
    "北境":{x:558,y:111,dx:0,dy:42}, "华夏":{x:657,y:291,dx:0,dy:45},
    "东瀛":{x:836,y:264,dx:33,dy:22}, "南洋":{x:700,y:476,dx:-9,dy:46},
  };
  const COUNTRY_SHAPES = {
    "华夏":"M161 108 191 89 228 104 263 77 308 88 336 70 371 91 409 79 449 100 483 86 519 109 559 105 581 128 624 115 656 137 699 142 715 167 754 174 765 205 806 218 794 249 818 275 805 300 822 326 797 350 803 379 768 401 770 431 736 442 713 476 674 470 646 506 607 493 577 523 537 509 510 531 470 515 433 521 413 496 374 500 353 475 320 481 301 456 266 457 252 428 219 416 219 386 188 367 201 333 175 307 187 276 160 256 175 227 151 201 170 174 150 145Z",
    "法兰西":"M279 121 322 102 365 114 391 87 429 102 460 86 488 111 523 105 550 129 590 132 610 158 651 161 665 192 697 211 685 242 713 267 699 293 718 324 699 348 705 380 677 398 670 430 633 445 612 478 574 472 548 498 511 489 476 511 442 492 405 500 382 477 344 481 323 454 294 446 297 416 270 393 282 362 257 336 274 305 252 279 270 250 251 223 270 195 256 168Z",
    "星联":"M150 146 180 115 214 113 240 85 281 94 304 75 337 95 371 85 402 104 446 98 468 120 511 110 543 137 585 132 610 156 648 150 672 179 709 179 724 211 763 223 748 254 779 277 764 308 780 334 757 359 763 385 733 411 742 441 710 456 694 489 655 483 626 505 592 487 563 506 524 489 487 504 459 481 419 486 388 463 353 470 325 444 288 442 273 412 238 405 233 375 205 362 214 333 185 315 200 284 176 259 184 231 161 209 170 179Z",
    "东瀛":"M652 104 682 91 707 111 705 141 681 167 679 197 651 217 648 247 623 270 622 300 597 328 583 357 559 372 547 401 522 413 502 446 474 453 455 481 427 485 410 467 419 439 445 423 455 394 481 378 489 350 514 337 518 306 544 289 550 257 575 239 579 210 606 192 608 162 638 145Z M373 472 399 464 415 481 408 503 385 515 369 505 347 518 331 503 345 486Z M702 69 725 64 746 84 735 106 710 103Z",
    "南洋":"M302 350 338 327 375 335 403 319 434 336 465 331 483 357 508 363 515 392 494 413 468 416 448 436 414 427 392 447 358 434 329 439 316 416 291 400 299 376Z M569 186 595 161 629 168 650 151 681 168 713 164 734 185 762 197 752 224 766 245 745 270 715 270 693 292 663 280 635 289 618 267 588 263 587 235 566 218Z M569 471 599 454 626 463 652 451 682 469 705 465 726 484 713 507 686 511 666 533 639 523 615 534 596 515 571 512 558 492Z M229 314 246 306 263 317 259 337 242 344 226 334Z M782 357 807 350 828 370 814 394 790 392Z",
    "北境":"M196 120 222 101 251 113 280 90 314 105 342 84 372 101 406 91 435 111 470 97 502 115 534 99 565 118 603 105 634 130 669 124 694 147 730 150 744 182 777 197 767 226 796 248 781 275 803 302 783 325 789 354 762 376 761 408 727 424 709 456 674 450 642 480 608 470 574 492 542 477 509 497 474 482 439 491 414 469 375 471 351 447 317 450 295 425 263 420 252 391 220 376 228 344 202 321 215 289 190 268 206 238 184 216 202 187 183 160Z",
  };

  function definitions(id) {
    return `<defs>
      <pattern id="${id}-grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" class="ca-grid-line"/></pattern>
      <pattern id="${id}-sea" width="92" height="64" patternUnits="userSpaceOnUse"><path d="M10 26q8-5 16 0t16 0M57 49q6-4 12 0t12 0" class="ca-wave"/></pattern>
      <pattern id="${id}-grain" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="2" cy="3" r=".5"/><circle cx="8" cy="9" r=".4"/></pattern>
      <symbol id="${id}-tree" viewBox="-9 -14 18 28"><path d="M0-13-6-4h3l-6 9h6l-5 6H8L3 5h6L3-4h3Z"/><path d="M0 9v5" class="ca-tree-trunk"/></symbol>
      <symbol id="${id}-mountain" viewBox="-17 -16 34 32"><path d="M-17 15 0-15 17 15Z" class="ca-mountain-face" fill="var(--ca-highland)" stroke="var(--ca-ink-soft)" stroke-width=".75"/><path d="M-17 15 0-15 2-4 7 2 17 15" class="ca-mountain-ridge" fill="none" stroke="var(--ca-ink-soft)" stroke-width=".7"/><path d="m-5-6 5-9 5 10-5-2-3 4Z" class="ca-snow" fill="var(--ca-land-light)" stroke="none"/></symbol>
      <symbol id="${id}-campus" viewBox="-12 -12 24 24"><path d="M-10-3 0-9 10-3M-8-1v9M-3-1v9M3-1v9M8-1v9M-11 9h22M-9-1H9"/></symbol>
      <symbol id="${id}-city" viewBox="-12 -12 24 24"><path d="M-9 10V-3h8v13M-1 10V-10H9v20M-6 0v2m0 3v2M2-6h4M2-2h4M2 2h4M2 6h4"/></symbol>
      <symbol id="${id}-culture" viewBox="-12 -12 24 24"><path d="M-10-4 0-10 10-4M-9-2H9M-7-2v10M0-2v10M7-2v10M-10 9h20"/></symbol>
      <symbol id="${id}-leisure" viewBox="-12 -12 24 24"><path d="M-2 5V-8l11-2v12M-2-4l11-2"/><ellipse cx="-5" cy="6" rx="4" ry="3"/><ellipse cx="6" cy="3" rx="4" ry="3"/></symbol>
      <symbol id="${id}-transport" viewBox="-12 -12 24 24"><rect x="-8" y="-10" width="16" height="17" rx="4"/><path d="M-8-3H8M-4 7l-3 4M4 7l3 4M-4 2h1m6 0h1"/></symbol>
      <symbol id="${id}-nature" viewBox="-12 -12 24 24"><path d="M0-11-7-2h3l-6 8H10L4-2h3ZM0 6v5"/></symbol>
      <symbol id="${id}-secret" viewBox="-12 -12 24 24"><path d="m-9-1 14-7 4 7-14 7ZM-1 4l-5 7M0 4l5 7"/></symbol>
    </defs>`;
  }

  function compass(x = 887, y = 86) {
    return `<g class="ca-compass" transform="translate(${x} ${y})" aria-hidden="true"><circle r="29"/><circle r="23"/><path d="M0-38 7-8 0-1-7-8ZM0 38 7 8 0 1-7 8Z"/><path class="ca-compass-light" d="m-38 0 30-7 7 7-7 7Zm76 0L8-7 1 0l7 7Z"/><text y="-46" text-anchor="middle">北</text><circle r="3"/></g>`;
  }
  function sheet(id, title, subtitle, body, opts = {}) {
    const compact = !!opts.compact;
    const controls = compact ? "" : `<div class="ca-map-controls" data-atlas-control="tools" role="group" aria-label="地图视角"><button type="button" data-map-action="in" aria-label="放大地图" title="放大地图">＋</button><button type="button" data-map-action="out" aria-label="缩小地图" title="缩小地图">−</button><button type="button" data-map-action="reset" aria-label="恢复地图视角" title="恢复地图视角">100%</button><details class="ca-pan-menu"><summary aria-label="平移地图" title="平移地图">移动</summary><div><button type="button" data-map-action="north" aria-label="地图向北移动">↑</button><button type="button" data-map-action="west" aria-label="地图向西移动">←</button><button type="button" data-map-action="east" aria-label="地图向东移动">→</button><button type="button" data-map-action="south" aria-label="地图向南移动">↓</button></div></details></div>`;
    return `<div class="ca-map${compact ? " ca-compact" : ""}" data-map-level="${esc(opts.level || "city")}"><svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" class="atlas-svg cartography${compact ? " compact" : ""}" role="group" aria-label="${esc(title)}" data-ca-base="0 0 ${W} ${H}">
      <title>${esc(title)}</title><desc>${esc(subtitle)}。选择地图标记查看目的地。可以使用放大、缩小和移动按钮调整视角。</desc>${definitions(id)}
      <rect width="960" height="620" class="ca-ocean"/><rect width="960" height="620" fill="url(#${id}-sea)"/><rect width="960" height="620" fill="url(#${id}-grid)"/>
      <defs><clipPath id="${id}-extent"><rect width="960" height="620"/></clipPath></defs><g clip-path="url(#${id}-extent)">${body}</g><rect x="15" y="15" width="930" height="590" rx="2" class="ca-sheet-border"/>
      <g class="ca-cartouche" aria-hidden="true"><path d="M34 34H257M34 38v43"/><text x="48" y="64" class="ca-sheet-title">${esc(title)}</text><text x="49" y="85" class="ca-sheet-subtitle">${esc(subtitle)}</text></g>
      ${compact ? "" : `${compass()}<g class="ca-scale" transform="translate(45 558)" aria-hidden="true"><path d="M0 0V8H120V0M60 3V8"/><text y="27">${esc(opts.scale || "旅行地理示意")}</text></g>`}
    </svg>${controls}${compact ? "" : `<div class="ca-map-caption"><span class="ca-caption-pin"></span>选地点查看行程<span class="ca-caption-drag"> · 可缩放、拖动地图</span></div>`}</div>`;
  }
  function ridge(id, x, y, count, size = 24, step = 23, slope = 0) {
    return `<g class="ca-mountains" aria-hidden="true">${Array.from({length:count}, (_, i) => `<use href="#${id}-mountain" x="${x + i * step}" y="${y + Math.sin(i * 1.8) * 9 + i * slope}" width="${size}" height="${size}"/>`).join("")}</g>`;
  }
  function trees(id, x, y, count = 12, spread = 85, seed = 1) {
    const random = seedRand(seed);
    return `<g class="ca-woodland" aria-hidden="true">${Array.from({length:count}, () => { const width = 9 + random() * 7; return `<use href="#${id}-tree" x="${round(x + random() * spread)}" y="${round(y + random() * spread * .55)}" width="${round(width)}" height="${round(width * 1.4)}"/>`; }).join("")}</g>`;
  }
  function contours(seed = 1, wide = true) {
    const random = seedRand(seed);
    return `<g class="ca-contours" aria-hidden="true">${Array.from({length:7}, (_, i) => {
      const y = 120 + i * 58, a = 40 + random() * 60;
      return `<path d="M${wide ? 35 : 150} ${y}C210 ${y-a} 245 ${y+a} 380 ${y-15}S620 ${y-a} 730 ${y+12}S855 ${y+50} 925 ${y-7}"/>`;
    }).join("")}</g>`;
  }
  function flight(a, b, bend = -70) {
    const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2 + bend;
    return `<path class="ca-flight" d="M${a.x} ${a.y}Q${round(cx)} ${round(cy)} ${b.x} ${b.y}"/>`;
  }
  function countryMarker(name, position, current, count) {
    const {x, y, dx = 0, dy = 42} = position;
    return `<g class="mcountry ca-country-pin${current ? " current" : ""}" data-country="${esc(name)}" role="button" tabindex="0" aria-label="${esc(name)}${current ? "，当前所在" : "，查看详情"}" transform="translate(${x} ${y})"><title>${esc(name)} · ${count}座城市</title><circle r="25" class="ca-marker-hit"/><circle r="13" class="ca-country-halo"/><circle r="6" class="ca-country-center"/><g transform="translate(${dx} ${dy})"><text text-anchor="middle" class="ca-country-title">${esc(name)}</text><text text-anchor="middle" y="20" class="ca-country-subtitle">${count} 座城市${current ? " · 你在这里" : ""}</text></g></g>`;
  }
  function world(state) {
    const id = "ca-world", loc = location(state);
    const available = countries(state);
    const land = WORLD_LANDS.map((l, i) => {
      const whole = `${l.d} ${l.islands || ""}`;
      return `<g class="ca-country-land ca-land-${i}" aria-hidden="true"><path d="${whole}" class="ca-coast-shadow"/><path d="${whole}" class="ca-coast-shelf"/><path d="${whole}" class="ca-land"/><clipPath id="${id}-${i}"><path d="${whole}"/></clipPath><g clip-path="url(#${id}-${i})">${contours(i + 31)}<rect width="960" height="620" fill="url(#${id}-grain)" class="ca-grain"/></g></g>`;
    }).join("");
    const terrain = ridge(id, 119, 128, 6, 22, 18, 4) + ridge(id, 555, 236, 5, 20, 21, 6) + ridge(id, 496, 93, 6, 17, 19) + trees(id, 146, 265, 16, 65, 5) + trees(id, 640, 326, 20, 68, 8) + trees(id, 368, 218, 9, 40, 11);
    const seaLabels = `<g class="ca-water-labels" aria-hidden="true"><text x="309" y="390" transform="rotate(-15 309 390)">长 风 洋</text><text x="868" y="444" transform="rotate(-9 868 444)">东 海</text><text x="511" y="545">南 境 洋</text><text x="240" y="83" class="ca-water-small">北方海域</text></g>`;
    const routes = `<g aria-hidden="true">${flight(WORLD_POINTS["星联"],WORLD_POINTS["华夏"],-112)}${flight(WORLD_POINTS["华夏"],WORLD_POINTS["法兰西"],-78)}${flight(WORLD_POINTS["华夏"],WORLD_POINTS["东瀛"],-42)}${flight(WORLD_POINTS["华夏"],WORLD_POINTS["南洋"],43)}${flight(WORLD_POINTS["北境"],WORLD_POINTS["法兰西"],-50)}</g>`;
    const pins = available.map((c, i) => countryMarker(c.name, WORLD_POINTS[c.name] || {x:100+i*125,y:310}, c.name === loc.country, cities(state,c.name).length)).join("");
    const oceanArt = `<g class="ca-sailing" transform="translate(340 464)" aria-hidden="true"><path d="m-17 5 7 10h29l9-10ZM1 2V-31L-14 2ZM5-29 21 2H5Z"/><path d="M-25 21q8-5 16 0t16 0 16 0"/></g><g class="ca-coordinate-labels" aria-hidden="true">${[160,320,480,640,800].map((x,i)=>`<text x="${x}" y="602" text-anchor="middle">${(i-2)*45}°</text>`).join("")}</g>`;
    const cityCount=available.reduce((n,c)=>n+cities(state,c.name).length,0);
    return sheet(id,"世界旅行图",`${available.length}个国家 · ${cityCount}座城市 · 每一段人生都有新的坐标`,land+terrain+routes+seaLabels+oceanArt+pins,{level:"world",scale:"国际航线 / 海陆示意"});
  }

  const COUNTRY_RIVERS = {
    "华夏":"M340 112C414 197 337 224 449 275S594 307 624 365 718 386 790 415",
    "法兰西":"M365 128C469 186 387 252 507 293S590 374 659 440",
    "星联":"M325 114C404 208 342 260 467 305S580 386 695 436",
    "北境":"M347 141C442 216 369 266 499 312S585 401 688 441",
  };
  function countryPoint(country, city) {
    const x = clamp(city.x ?? 50, 0, 100), y = clamp(city.y ?? 50, 0, 100);
    if (country === "东瀛") return {x: x > 48 ? 622 : 463, y:y < 50 ? 244 : 421};
    if (country === "南洋") return {x:y > 45 ? 411 : 669,y:y > 45 ? 384 : 225};
    return {x:150+x*6.7,y:103+y*4.25};
  }
  function cityMarker(name, p, current, id, cityCount) {
    return `<g class="mcity ca-city-pin${current ? " current" : ""}" data-city="${esc(name)}" role="button" tabindex="0" aria-label="${esc(name)}${current ? "，当前所在" : "，查看详情"}" transform="translate(${round(p.x)} ${round(p.y)})"><title>${esc(name)} · ${cityCount}个去处</title><circle r="26" class="ca-marker-hit"/><path d="M0-14C-15-14-20-1 0 20 20-1 15-14 0-14Z" class="ca-city-marker"/><circle cy="-1" r="5" class="ca-city-marker-center"/><rect x="18" y="-15" width="${Math.max(70, name.length * 19 + 15)}" height="43" rx="4" class="ca-label-paper"/><text x="26" y="3" class="ca-city-title">${esc(name)}</text><text x="26" y="21" class="ca-city-subtitle">${cityCount}个去处</text></g>`;
  }
  function country(state, name) {
    const id = "ca-country-" + hash(name), loc = location(state);
    const shape = COUNTRY_SHAPES[name] || COUNTRY_SHAPES["华夏"];
    const points = cities(state,name).map(c=>({...c,...countryPoint(name,c)}));
    const roads = points.slice(1).map((c,i)=> {
      const a = points[i], bend = (i % 2 ? -1 : 1) * 35;
      const d = `M${round(a.x)} ${round(a.y)}Q${round((a.x+c.x)/2+bend)} ${round((a.y+c.y)/2-bend)} ${round(c.x)} ${round(c.y)}`;
      return `<path d="${d}" class="ca-road-edge"/><path d="${d}" class="ca-highway"/><path d="${d}" class="ca-rail"/>`;
    }).join("");
    const topography = `<path d="${shape}" class="ca-coast-shadow"/><path d="${shape}" class="ca-coast-shelf"/><path d="${shape}" class="ca-land"/><clipPath id="${id}-land"><path d="${shape}"/></clipPath><g clip-path="url(#${id}-land)"><path d="M144 116Q397 60 459 192T391 435L172 506Z" class="ca-highlands"/><path d="M630 91Q560 250 744 390T642 541L860 547V106Z" class="ca-lowlands"/>${contours(hash(name))}<rect width="960" height="620" fill="url(#${id}-grain)" class="ca-grain"/>${ridge(id,222,171,7,35,30,13)}${ridge(id,294,292,5,28,28,9)}${trees(id,572,150,35,134,hash(name))}${trees(id,370,393,24,122,hash(name)+9)}${COUNTRY_RIVERS[name] ? `<path d="${COUNTRY_RIVERS[name]}" class="ca-river-bank"/><path d="${COUNTRY_RIVERS[name]}" class="ca-river"/>` : ""}${roads}</g>`;
    const terrainLabels = `<g class="ca-region-labels" aria-hidden="true"><text x="290" y="166" transform="rotate(13 290 166)">${name === "北境" ? "冰 脊 山 脉" : name === "东瀛" ? "青 岚 群 山" : "西 岭 山 脉"}</text><text x="548" y="451">${name === "南洋" ? "珊 瑚 海" : name === "北境" ? "北 部 林 原" : "南 部 平 原"}</text></g><g class="ca-water-labels" aria-hidden="true"><text x="829" y="420" transform="rotate(90 829 420)">${name === "星联" ? "长 风 洋" : name === "北境" ? "浮 冰 海" : "远 航 海"}</text></g>`;
    const pins = points.map(c=>cityMarker(c.name,c,c.name===loc.city,id,list(state).filter(p=>p.city===c.name).length)).join("");
    return sheet(id,`${name}旅行图`,`${points.length}座城市 · 铁路与公路连接每一次出发`,topography+terrainLabels+pins,{level:"country",scale:"城际交通 / 地形示意"});
  }

  function overlap(a,b,pad=3) { return a.x < b.x+b.w+pad && a.x+a.w+pad > b.x && a.y < b.y+b.h+pad && a.y+a.h+pad > b.y; }
  function labelWidth(name) { return Math.min(190,Array.from(String(name)).reduce((n,c)=>n+(/\p{Script=Han}/u.test(c)?13.5:7.8),0)+17); }
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
  function buildingBlocks(seed) {
    const random=seedRand(seed);
    const blocks=[];
    for(let row=0;row<7;row++)for(let col=0;col<11;col++){
      const x=40+col*83+(row%2)*8, y=99+row*63;
      if((col===1&&row<3)||(col===4&&row>3)||(col>8&&row<3))continue;
      const bw=43+random()*20,bh=26+random()*20;
      blocks.push(`<g class="ca-block${(row+col)%4===0?" ca-block-special":""}" transform="translate(${round(x)} ${round(y)}) rotate(${(col%3-1)*2})"><rect width="${round(bw)}" height="${round(bh)}" rx="2"/><path d="M${round(bw*.55)} 2V${round(bh-2)}M2 ${round(bh*.58)}H${round(bw-2)}"/></g>`);
    }
    return `<g class="ca-blocks" aria-hidden="true">${blocks.join("")}</g>`;
  }
  function cityBase(id,name) {
    const seed=hash(name), coastal=/魔都|江海|海湾|蔚蓝|新港|星湾|狮城|椰湾|松港/.test(name);
    const river=coastal?"M708-20C783 101 689 158 737 260S677 402 731 477 821 550 772 650":"M685-20C562 104 726 174 630 262S682 399 597 480 616 564 565 650";
    const parks=`<g class="ca-parks" aria-hidden="true"><path d="M69 119 181 119 185 214 158 239 75 223Z"/><path d="M348 385 449 378 468 474 428 520 346 506Z"/><path d="M770 101 874 108 891 198 831 215 779 178Z"/></g>`;
    const lanes = [133,244,362,481].map((y,i)=>`M0 ${y}C235 ${y-21+i*3} 291 ${y+27} 490 ${y+4}S790 ${y-13} 960 ${y+11}`)
      .concat([205,341,508,832].map((x,i)=>`M${x} 0C${x+28} 170 ${x-34} 205 ${x+8} 329S${x-19} 505 ${x+10} 620`));
    const roads=lanes.map((d,i)=>`<path d="${d}" class="ca-street-edge"/><path d="${d}" class="${i<4?"ca-main-street":"ca-side-street"}"/>`).join("");
    const rail="M-40 552C202 531 319 561 448 529S753 532 1000 499";
    const sidePaths=["M75 0V590","M436 80V556","M927 90 890 528","M18 305H930","M35 419H885","M100 190H895"].map(d=>`<path d="${d}" class="ca-lane"/>`).join("");
    const bridgeStrokes=[244,362,481].map(y=>`<path d="M560 ${y+3}H780" class="ca-bridge-edge"/><path d="M560 ${y+3}H780" class="ca-bridge"/>`).join("");
    const labels=`<g class="ca-street-labels" aria-hidden="true"><text x="310" y="249" transform="rotate(2 310 249)">${name === "京都" ? "银 杏 大 道" : name+"大 道"}</text><text x="774" y="375">滨 河 路</text><text x="220" y="329" transform="rotate(-88 220 329)">中 央 大 街</text><text x="106" y="410">老 城 区</text><text x="347" y="176">文 化 学 园</text><text x="744" y="453">新 城 商 务 区</text><text x="378" y="460" class="ca-park-label">城 市 绿 地</text></g>`;
    return `<rect width="960" height="620" class="ca-city-ground"/>${coastal?`<path d="M819 0H960V620H847Q885 470 831 320T819 0Z" class="ca-coastal-water"/>`:""}${buildingBlocks(seed)}${parks}${trees(id,81,134,23,84,seed)}${trees(id,359,409,23,74,seed+2)}${trees(id,793,120,19,60,seed+3)}<g aria-hidden="true">${sidePaths}${roads}<path d="${river}" class="ca-city-river-bank"/><path d="${river}" class="ca-city-river"/>${bridgeStrokes}<path d="${rail}" class="ca-city-rail-edge"/><path d="${rail}" class="ca-city-rail"/></g>${labels}<g class="ca-river-label" transform="translate(652 339) rotate(24)" aria-hidden="true"><text>${coastal?"滨 江":"清 溪 河"}</text></g>`;
  }
  function placeMarker(p,current,id,compact) {
    const type=["campus","city","culture","leisure","transport","nature","secret"].includes(p.type)?p.type:"city";
    const box=p.box;
    const label=compact?(current?`<text x="${p.x}" y="${p.y+42}" text-anchor="middle" class="ca-mini-label">${esc(p.name)}</text>`:""):`<g class="ca-place-label"><rect x="${round(box.x)}" y="${round(box.y)}" width="${round(box.w)}" height="${box.h}" rx="3" class="ca-label-paper" data-map-label-box="${[box.x,box.y,box.w,box.h].map(round).join(',')}"/><text x="${round(box.x+8)}" y="${round(box.y+17.5)}">${esc(p.name)}</text></g>`;
    return `<g class="mplace ca-place-pin ca-type-${type}${current?" current":""}${p.discovered?" visited":""}" data-place="${esc(p.name)}" data-city="${esc(p.city)}" data-map-point="${p.x},${p.y}" role="button" tabindex="0" aria-label="${esc(p.name)}${current?"，当前所在":"，查看详情"}"><title>${esc(p.name)}${current?" · 当前所在":""}</title><circle cx="${p.x}" cy="${p.y}" r="25" class="ca-marker-hit"/>${current?`<circle cx="${p.x}" cy="${p.y}" r="24" class="ca-current-ring"/>`:""}<circle cx="${p.x}" cy="${p.y}" r="17" class="ca-place-symbol-bg"/><use href="#${id}-${type}" x="${p.x-10}" y="${p.y-10}" width="20" height="20" class="ca-place-symbol"/>${label}</g>`;
  }
  function city(state,name,compact=false,typeFilter="") {
    const id="ca-city-"+hash(name)+(compact?"-mini":""),loc=location(state);
    const places=list(state).filter(p=>p.city===name&&(!typeFilter||compact||p.type===typeFilter));
    const pins=placeLayout(places).map(p=>placeMarker(p,p.name===loc.place,id,compact)).join("");
    return sheet(id,`${name}城市地图`,`${places.length}个去处 · 街巷里，生活正在发生`,cityBase(id,name)+pins,{level:"city",compact,scale:"街区与地标 / 步行地图"});
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
