package com.legacy.shop;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Vector;
import java.io.FileWriter;

public class LegacyOrderService {

    // Raw types — pas de generics
    private static HashMap orders = new HashMap();
    private static Vector productCache = new Vector();
    private static List pendingOrders = new ArrayList();

    // Constante mal déclarée
    public static String MAX_ORDERS = "100";

    public String getOrderId(Object order) {
        // Null check manuel au lieu de Optional
        if (order == null) {
            return null;
        }
        return order.toString();
    }

    // Boucle for old-style au lieu de for-each
    public double calculateTotal(List items) {
        double total = 0;
        for (int i = 0; i < items.size(); i++) {
            Object item = items.get(i);
            total = total + Double.parseDouble(item.toString());
        }
        return total;
    }

    // String concat dans boucle (très mauvais pour la performance)
    public String buildInvoice(List lineItems) {
        String invoice = "";
        for (int i = 0; i < lineItems.size(); i++) {
            invoice = invoice + "Line " + i + ": " + lineItems.get(i).toString() + "\n";
        }
        return invoice;
    }

    // Date deprecated au lieu de java.time
    public boolean isOrderExpired(Date orderDate) {
        Date now = new Date();
        long diff = now.getTime() - orderDate.getTime();
        return diff > 86400000L;
    }

    // Catch Exception générique — avale tous les types d'erreurs
    public void saveOrder(Object order) {
        try {
            connectToDatabase(order);
        } catch (Exception e) {
            // Mauvaise pratique : printStackTrace au lieu de logger
            e.printStackTrace();
        }
    }

    // Resource leak : FileWriter jamais fermé
    public void writeOrderLog(String message) {
        try {
            FileWriter fw = new FileWriter("orders.log", true);
            fw.write(message + "\n");
            // fw.close() oublié !
        } catch (Exception e) {
            System.out.println("Erreur log : " + e.getMessage());
        }
    }

    // Comparaison de String avec == au lieu de .equals()
    public boolean isVipOrder(String orderType) {
        if (orderType == "VIP") {
            return true;
        }
        return false;
    }

    // Return null au lieu d'Optional
    public Object findOrder(String orderId) {
        if (orders.containsKey(orderId)) {
            return orders.get(orderId);
        }
        return null;
    }

    // Filtrage old-style sans Stream API
    public List getExpiredOrders(List allOrders, Date cutoff) {
        List expired = new ArrayList();
        for (int i = 0; i < allOrders.size(); i++) {
            Object o = allOrders.get(i);
            if (o != null) {
                expired.add(o);
            }
        }
        return expired;
    }

    // Cast dangereux sans vérification instanceof
    public void processPayment(Object payment) {
        String amount = (String) payment;
        System.out.println("Paiement : " + amount);
    }

    // Synchronisation inutile sur méthode entière
    public synchronized void addToCache(Object product) {
        productCache.add(product);
        orders.put(product.toString(), product);
    }

    private void connectToDatabase(Object data) throws Exception {
        throw new Exception("DB connection failed for: " + data);
    }

    public static void main(String[] args) {
        LegacyOrderService service = new LegacyOrderService();

        // Test calculateTotal
        List items = new ArrayList();
        items.add("10.5");
        items.add("25.0");
        items.add("7.99");
        System.out.println("Total : " + service.calculateTotal(items));

        // Test buildInvoice
        System.out.println(service.buildInvoice(items));

        // Test isOrderExpired
        Date oldDate = new Date(System.currentTimeMillis() - 200000000L);
        System.out.println("Expiré : " + service.isOrderExpired(oldDate));

        // Test isVipOrder (bug == sur String)
        String type = new String("VIP");
        System.out.println("VIP (bug) : " + service.isVipOrder(type));

        // Test saveOrder (va logger une exception)
        service.saveOrder("ORDER-001");
    }
}
