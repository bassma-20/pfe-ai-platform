package com.bank.service;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;

public class BankAccountService {

    // Raw types sans generics
    private HashMap accounts = new HashMap();
    private List transactions = new ArrayList();

    // Constante mal déclarée
    public static String CURRENCY = "EUR";

    // Null check manuel
    public String getAccountHolder(Object account) {
        if (account == null) {
            return "Unknown";
        }
        return account.toString();
    }

    // Date deprecated
    public boolean isAccountExpired(Date createdDate) {
        Date now = new Date();
        long diff = now.getTime() - createdDate.getTime();
        return diff > 31536000000L; // 1 an en ms
    }

    // String concat dans boucle
    public String getTransactionHistory(List items) {
        String history = "";
        for (int i = 0; i < items.size(); i++) {
            history = history + "TX" + i + ": " + items.get(i) + "\n";
        }
        return history;
    }

    // Comparaison String avec ==
    public boolean isPremiumAccount(String type) {
        if (type == "PREMIUM") {
            return true;
        }
        return false;
    }

    // catch Exception générique + printStackTrace
    public void deposit(String accountId, double amount) {
        try {
            processDeposit(accountId, amount);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // Resource leak : connection jamais fermée
    public void saveTransaction(String tx) {
        try {
            java.io.FileWriter fw = new java.io.FileWriter("transactions.log", true);
            fw.write(tx + "\n");
            // fw.close() oublié !
        } catch (Exception e) {
            System.out.println("Erreur : " + e.getMessage());
        }
    }

    // Boucle old-style au lieu de Stream
    public List getPositiveBalances(List balances) {
        List result = new ArrayList();
        for (int i = 0; i < balances.size(); i++) {
            Double bal = (Double) balances.get(i); // cast dangereux
            if (bal > 0) {
                result.add(bal);
            }
        }
        return result;
    }

    // Return null au lieu d'Optional
    public Object findAccount(String id) {
        if (accounts.containsKey(id)) {
            return accounts.get(id);
        }
        return null;
    }

    private void processDeposit(String id, double amount) throws Exception {
        if (amount <= 0) throw new Exception("Montant invalide");
        accounts.put(id, amount);
    }

    public static void main(String[] args) {
        BankAccountService service = new BankAccountService();

        // Test getTransactionHistory
        List txList = new ArrayList();
        txList.add("100.00 EUR");
        txList.add("250.50 EUR");
        txList.add("75.00 EUR");
        System.out.println(service.getTransactionHistory(txList));

        // Test isPremiumAccount (bug == String)
        String type = new String("PREMIUM");
        System.out.println("Premium (bug): " + service.isPremiumAccount(type));

        // Test deposit valide
        service.deposit("ACC-001", 500.0);
        System.out.println("Compte ACC-001 : " + service.findAccount("ACC-001"));

        // Test deposit invalide (va logger exception)
        service.deposit("ACC-002", -100.0);

        // Test isAccountExpired
        Date oldDate = new Date(System.currentTimeMillis() - 40000000000L);
        System.out.println("Expiré : " + service.isAccountExpired(oldDate));
    }
}
