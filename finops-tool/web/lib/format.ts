const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatUsd(value: number): string {
  return usd.format(value);
}

/** "orphaned_ebs_volumes" -> "Orphaned EBS volumes" */
export function humanizeRuleId(ruleId: string): string {
  const words = ruleId.split("_");
  return words
    .map((w, i) => {
      // Acronyms keep their casing; a trailing plural "s" stays lowercase (EIPs).
      const acronym = /^(ebs|eip|ec2|s3|rds|elb|nat|ami)(s?)$/i.exec(w);
      if (acronym) return acronym[1].toUpperCase() + acronym[2];
      return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w;
    })
    .join(" ");
}
